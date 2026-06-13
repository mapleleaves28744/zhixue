import type { AgentTaskEvent } from "@/types/agent"

export type AgentTimelineStepStatus = "running" | "complete" | "error" | "waiting"

export interface AgentTimelineStep {
  id: string
  kind: string
  title: string
  subtitle?: string
  status: AgentTimelineStepStatus
  icon: string
  detailText?: string
}

function stringify(value: unknown): string {
  if (value == null) return ""
  if (typeof value === "string") return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {}
}

function firstText(...values: unknown[]): string {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value.trim()
  }
  return ""
}

function toolNameFrom(event: AgentTaskEvent): string {
  const data = event.data || {}
  const direct = firstText(data.tool_name, data.name)
  if (direct) return direct
  const toolCall = asRecord(data.tool_call)
  return firstText(toolCall.name, toolCall.tool_name) || "tool"
}

function countPlanSteps(data: Record<string, unknown>): number {
  const plan = Array.isArray(data.plan) ? data.plan.length : 0
  const toolCalls = Array.isArray(data.tool_calls) ? data.tool_calls.length : 0
  return Math.max(plan, toolCalls, 1)
}

function buildPlanDetail(data: Record<string, unknown>): string {
  const parts: string[] = []
  const summary = firstText(data.summary, data.message)
  if (summary) parts.push(`摘要\n${summary}`)
  if (data.reasoning_content) parts.push(`规划思路\n${stringify(data.reasoning_content)}`)
  if (Array.isArray(data.plan) && data.plan.length) {
    parts.push(`步骤\n${data.plan.map((step, index) => `${index + 1}. ${stringify(step)}`).join("\n")}`)
  }
  if (Array.isArray(data.tool_calls) && data.tool_calls.length) {
    parts.push(`工具调用\n${stringify(data.tool_calls)}`)
  }
  return parts.join("\n\n")
}

function buildToolDetail(
  start: AgentTaskEvent,
  completed?: AgentTaskEvent,
  observation?: AgentTaskEvent,
): string {
  const parts: string[] = []
  const args = start.data.arguments ?? start.data.input ?? start.data.tool_args
  if (args != null) parts.push(`输入参数\n${stringify(args)}`)
  if (completed) {
    const success = completed.data.success === false ? "失败" : "成功"
    const attempts = completed.data.attempts != null ? `，尝试 ${String(completed.data.attempts)} 次` : ""
    parts.push(`执行结果\n${success}${attempts}`)
    if (completed.data.error_message) parts.push(`错误信息\n${String(completed.data.error_message)}`)
    if (Array.isArray(completed.data.artifact_refs) && completed.data.artifact_refs.length) {
      parts.push(`产物引用\n${stringify(completed.data.artifact_refs)}`)
    }
  }
  if (observation?.data.output != null) parts.push(`观察输出\n${stringify(observation.data.output)}`)
  if (Array.isArray(observation?.data.evidence) && observation.data.evidence.length) {
    parts.push(`证据\n${stringify(observation.data.evidence)}`)
  }
  return parts.join("\n\n")
}

function multimodalStatus(data: Record<string, unknown>): AgentTimelineStepStatus {
  const stage = String(data.stage || "").toLowerCase()
  if (stage.includes("fail") || stage.includes("error")) return "error"
  if (Number(data.progress ?? 0) >= 100) return "complete"
  if (stage.includes("complete") || stage.includes("succeeded") || stage.includes("done")) return "complete"
  return "running"
}

/** 同一 job_id 的进度事件只保留最新一条，避免时间线重复堆叠。 */
export function collapseMultimodalProgressEvents(events: AgentTaskEvent[]): AgentTaskEvent[] {
  const result: AgentTaskEvent[] = []
  const indexByJobId = new Map<string, number>()

  for (const event of events) {
    if (event.type !== "multimodal_progress") {
      result.push(event)
      continue
    }
    const jobId = String(event.data?.job_id || "")
    if (!jobId) {
      result.push(event)
      continue
    }
    const existingIndex = indexByJobId.get(jobId)
    if (existingIndex != null) {
      result[existingIndex] = event
    } else {
      indexByJobId.set(jobId, result.length)
      result.push(event)
    }
  }

  return result
}

export function buildAgentStepTimeline(events: AgentTaskEvent[], streaming: boolean): AgentTimelineStep[] {
  const steps: AgentTimelineStep[] = []
  const consumed = new Set<number>()

  collapseMultimodalProgressEvents(events).forEach((event, index) => {
    if (consumed.has(index) || event.type === "heartbeat") return
    const data = event.data || {}

    if (event.type === "plan_created" || event.type === "replanned") {
      const count = countPlanSteps(data)
      steps.push({
        id: `${event.type}-${index}`,
        kind: "plan",
        title: event.type === "replanned" ? `重新查看 ${count} 个步骤` : `查看 ${count} 个步骤`,
        subtitle: firstText(data.summary, data.message),
        status: "complete",
        icon: "visibility",
        detailText: buildPlanDetail(data),
      })
      return
    }

    if (event.type === "tool_started") {
      const name = toolNameFrom(event)
      let completedIndex = -1
      let observationIndex = -1
      for (let i = index + 1; i < events.length; i += 1) {
        if (events[i].type === "tool_started") break
        if (events[i].type === "tool_completed" && toolNameFrom(events[i]) === name && completedIndex < 0) {
          completedIndex = i
          consumed.add(i)
        }
        if (events[i].type === "observation" && toolNameFrom(events[i]) === name && observationIndex < 0) {
          observationIndex = i
          consumed.add(i)
        }
      }
      const completed = completedIndex >= 0 ? events[completedIndex] : undefined
      const observation = observationIndex >= 0 ? events[observationIndex] : undefined
      steps.push({
        id: `tool-${index}`,
        kind: "tool",
        title: `执行 ${name}`,
        subtitle: completed
          ? completed.data.success === false
            ? String(completed.data.error_message || "工具执行失败")
            : "工具执行完成"
          : streaming
            ? "工具调用中"
            : "工具已开始",
        status: completed ? (completed.data.success === false ? "error" : "complete") : "running",
        icon: completed?.data.success === false ? "error" : "check_circle",
        detailText: buildToolDetail(event, completed, observation),
      })
      return
    }

    if (event.type === "tool_completed") {
      const failed = data.success === false
      steps.push({
        id: `tool-completed-${index}`,
        kind: "tool",
        title: `${failed ? "工具失败" : "工具完成"} ${toolNameFrom(event)}`,
        subtitle: failed ? String(data.error_message || "执行失败") : "执行成功",
        status: failed ? "error" : "complete",
        icon: failed ? "error" : "check_circle",
        detailText: stringify(data),
      })
      return
    }

    if (event.type === "observation") {
      steps.push({
        id: `observation-${index}`,
        kind: "observation",
        title: "整理工具结果",
        subtitle: firstText(data.message) || "观察输出已更新",
        status: "complete",
        icon: "visibility",
        detailText: stringify(data.output ?? data),
      })
      return
    }

    if (event.type === "multimodal_progress") {
      const jobId = String(data.job_id || index)
      steps.push({
        id: `multimodal-${jobId}`,
        kind: "media",
        title: firstText(data.message) || "多模态产物生成中",
        subtitle: data.progress != null ? `${String(data.stage || "progress")} · ${String(data.progress)}%` : String(data.stage || ""),
        status: multimodalStatus(data),
        icon: "movie",
        detailText: stringify(data),
      })
      return
    }

    if (event.type === "waiting_confirmation") {
      steps.push({
        id: `waiting-${index}`,
        kind: "confirmation",
        title: "等待你确认下一步",
        subtitle: firstText(data.message) || "高风险操作需要确认",
        status: "waiting",
        icon: "help",
        detailText: stringify(data.arguments || data),
      })
      return
    }

    if (event.type === "reviewed") {
      steps.push({
        id: `reviewed-${index}`,
        kind: "review",
        title: "Review 审查",
        subtitle: firstText(data.summary, data.message) || "已检查输出质量与依据",
        status: "complete",
        icon: "fact_check",
        detailText: stringify(data),
      })
      return
    }

    if (event.type === "memory_reflected") {
      steps.push({
        id: `memory-${index}`,
        kind: "memory",
        title: "更新长期记忆",
        subtitle: firstText(data.message) || "学习画像与记忆已反思",
        status: "complete",
        icon: "psychology",
        detailText: stringify(data),
      })
      return
    }

    if (event.type === "queued" || event.type === "planning") {
      steps.push({
        id: `${event.type}-${index}`,
        kind: "system",
        title: event.type === "queued" ? "任务已进入队列" : "深度思考",
        subtitle: firstText(data.message) || (event.type === "queued" ? "等待执行器接手" : "加载课程、资料、画像与上下文"),
        status: event.type === "queued" && streaming ? "running" : "complete",
        icon: event.type === "queued" ? "pending" : "psychology",
        detailText: stringify(data),
      })
      return
    }

    if (event.type === "completed") {
      steps.push({
        id: `completed-${index}`,
        kind: "terminal",
        title: "回答已生成",
        subtitle: "最终结果已写入对话",
        status: "complete",
        icon: "check_circle",
        detailText: stringify({ artifacts: data.artifacts, citations: data.citations }),
      })
      return
    }

    if (event.type === "failed" || event.type === "cancelled") {
      steps.push({
        id: `${event.type}-${index}`,
        kind: "terminal",
        title: event.type === "failed" ? "任务失败" : "任务已取消",
        subtitle: firstText(data.error_message, data.message),
        status: event.type === "failed" ? "error" : "complete",
        icon: event.type === "failed" ? "error" : "cancel",
        detailText: stringify(data),
      })
      return
    }

    steps.push({
      id: `${event.type}-${index}`,
      kind: "event",
      title: firstText(data.message) || event.type,
      status: "complete",
      icon: "auto_awesome",
      detailText: stringify(data),
    })
  })

  if (!steps.length && streaming) {
    return [
      {
        id: "booting",
        kind: "system",
        title: "智能体启动中",
        subtitle: "正在建立流式连接",
        status: "running",
        icon: "progress_activity",
      },
    ]
  }

  return steps
}
