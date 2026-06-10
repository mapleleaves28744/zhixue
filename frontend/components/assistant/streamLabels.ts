import type { AgentTaskEvent } from "@/types/agent"

const EVENT_LABELS: Record<string, string> = {
  queued: "任务排队",
  planning: "加载会话、课程、画像与长期记忆",
  plan_created: "生成执行计划",
  replanned: "重新规划",
  tool_started: "调用工具",
  tool_completed: "工具执行完成",
  observation: "整理工具结果",
  reviewed: "Review 审查",
  waiting_confirmation: "等待确认",
  multimodal_progress: "多模态生成",
  memory_reflected: "更新长期记忆",
  completed: "回答已生成",
  failed: "任务失败",
  cancelled: "已取消",
}

export function agentStatusLine(events: AgentTaskEvent[], streaming: boolean): string {
  if (!events.length) {
    return streaming ? "智能体启动中…" : "等待执行"
  }
  const last = events[events.length - 1]
  const label = EVENT_LABELS[last.type] || last.type

  if (last.type === "tool_started" || last.type === "tool_completed") {
    const tool = String(last.data.tool_name || "")
    return tool ? `${label} · ${tool}` : label
  }
  if (last.type === "plan_created" || last.type === "replanned") {
    const plan = (last.data.plan as string[]) || []
    const tools = (last.data.tool_calls as unknown[]) || []
    const count = Math.max(plan.length, tools.length)
    return count ? `${label} · ${count} 步` : label
  }
  if (last.type === "multimodal_progress") {
    return String(last.data.message || label)
  }
  if (last.type === "completed") {
    return "回答已生成"
  }
  if (last.type === "failed") {
    return String(last.data.error_message || "任务失败")
  }
  return String(last.data.message || label)
}

export function eventLabel(type: string): string {
  return EVENT_LABELS[type] || type
}

export function truncateText(text: string, max = 72): string {
  const normalized = text.replace(/\s+/g, " ").trim()
  if (normalized.length <= max) return normalized
  return `${normalized.slice(0, max)}…`
}
