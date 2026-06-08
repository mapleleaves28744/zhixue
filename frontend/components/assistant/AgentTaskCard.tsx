"use client"

import { useState } from "react"
import { MarkdownRenderer } from "@/components/markdown/MarkdownRenderer"
import { cn } from "@/lib/utils"
import type { AgentTask, AgentTaskEvent } from "@/types/agent"
import { ArtifactCard } from "./ArtifactCard"

const EVENT_LABELS: Record<string, string> = {
  queued: "任务排队",
  planning: "加载上下文",
  plan_created: "生成计划",
  replanned: "重新规划",
  tool_started: "调用工具",
  tool_completed: "工具完成",
  observation: "观察结果",
  reviewed: "Review 审查",
  waiting_confirmation: "等待确认",
  multimodal_progress: "多模态生成",
  completed: "完成",
  failed: "失败",
  cancelled: "已取消",
}

interface AgentTaskCardProps {
  task: AgentTask | null
  events: AgentTaskEvent[]
  finalAnswer: string
  streaming: boolean
  error?: string | null
  onApprove?: (approved: boolean) => void
}

export function AgentTaskCard({
  task,
  events,
  finalAnswer,
  streaming,
  error,
  onApprove,
}: AgentTaskCardProps) {
  const [expanded, setExpanded] = useState(false)
  const artifacts = (task?.plan_json?.artifact_refs as Record<string, unknown>[]) || []
  const citations = (task?.plan_json?.citations as Record<string, unknown>[]) || []
  const waiting = task?.status === "waiting_confirmation"

  return (
    <div className="glass-card max-w-[92%] rounded-3xl rounded-tl-md p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-bold text-primary">智能体任务</p>
          <p className="mt-1 text-xs text-outline">
            {task?.status || "running"} · 工具 {task?.tool_call_count ?? 0} 次 · 循环{" "}
            {task?.iteration_count ?? 0}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="rounded-full border border-white/80 bg-white/60 px-3 py-1 text-xs font-semibold text-outline hover:text-primary"
        >
          {expanded ? "收起详情" : "展开详情"}
        </button>
      </div>

      {expanded && (
        <div className="mt-3 max-h-60 space-y-2 overflow-y-auto rounded-2xl bg-white/40 p-3 text-xs">
          {events.map((evt, index) => (
            <div key={`${evt.type}-${index}`} className="border-b border-white/60 pb-2 last:border-0">
              <span className="font-bold text-primary">{EVENT_LABELS[evt.type] || evt.type}</span>
              {evt.type === "tool_started" && (
                <span className="ml-2 text-outline">{String(evt.data.tool_name || "")}</span>
              )}
              {evt.type === "observation" && evt.data.output != null && (
                <p className="mt-1 line-clamp-3 text-on-surface-variant">
                  {String(typeof evt.data.output === "string" ? evt.data.output : JSON.stringify(evt.data.output))}
                </p>
              )}
              {evt.type === "waiting_confirmation" && (
                <pre className="mt-1 overflow-x-auto rounded bg-white/70 p-2 text-[10px]">
                  {JSON.stringify(evt.data.arguments || {}, null, 2)}
                </pre>
              )}
            </div>
          ))}
          {!events.length && streaming && <p className="text-outline">正在接收 Agent 事件…</p>}
        </div>
      )}

      {waiting && onApprove && (
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={() => onApprove(true)}
            className="rounded-full bg-primary px-4 py-1.5 text-xs font-bold text-on-primary"
          >
            确认执行
          </button>
          <button
            type="button"
            onClick={() => onApprove(false)}
            className="rounded-full border border-outline/30 px-4 py-1.5 text-xs font-bold text-outline"
          >
            拒绝
          </button>
        </div>
      )}

      {artifacts.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {artifacts.map((ref, i) => (
            <ArtifactCard key={String(ref.asset_id || ref.resource_id || i)} artifact={ref} />
          ))}
        </div>
      )}

      {finalAnswer && (
        <div className="mt-4 border-t border-white/60 pt-4">
          <MarkdownRenderer content={finalAnswer} />
        </div>
      )}

      {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
      {streaming && !finalAnswer && (
        <p className={cn("mt-3 text-sm text-outline", !expanded && "line-clamp-2")}>
          Agent 正在规划与调用工具，完成后将在此显示回答…
        </p>
      )}

      {citations.length > 0 && (
        <details className="mt-3 text-xs text-outline">
          <summary className="cursor-pointer font-semibold">来源 ({citations.length})</summary>
          <ul className="mt-2 space-y-1">
            {citations.slice(0, 5).map((c, i) => (
              <li key={i}>{String(c.title || c.source_title || "课程资料")}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
