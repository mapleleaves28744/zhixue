"use client"

import { MarkdownRenderer } from "@/components/markdown/MarkdownRenderer"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import type { AgentTask, AgentTaskEvent } from "@/types/agent"
import { AgentEventDetail, taskStatusLabel } from "./AgentEventDetail"
import { ArtifactCard } from "./ArtifactCard"
import { extractSpeechAudio } from "./extractSpeechAudio"
import { InlineAudioPlayer } from "./InlineAudioPlayer"

interface ActivityDetailDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  subtitle?: string
  content?: string
  streaming?: boolean
  events?: AgentTaskEvent[]
  task?: AgentTask | null
  error?: string | null
  onApprove?: (approved: boolean) => void
}

export function ActivityDetailDialog({
  open,
  onOpenChange,
  title,
  subtitle,
  content,
  streaming,
  events = [],
  task,
  error,
  onApprove,
}: ActivityDetailDialogProps) {
  const artifacts = (task?.plan_json?.artifact_refs as Record<string, unknown>[]) || []
  const citations = (task?.plan_json?.citations as Record<string, unknown>[]) || []
  const decisionSummary = task?.plan_json?.decision_summary
    ? String(task.plan_json.decision_summary)
    : ""
  const waiting = task?.status === "waiting_confirmation"
  const stuckQueued = streaming && task?.status === "queued" && events.length <= 1
  const speechAudio = extractSpeechAudio(events, task)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-hidden p-0">
        <DialogHeader className="border-b border-white/60 px-6 py-4">
          <DialogTitle>{title}</DialogTitle>
          {subtitle ? <p className="text-xs text-outline">{subtitle}</p> : null}
          {task ? (
            <p className="text-[11px] text-outline">
              任务状态：{taskStatusLabel(task.status)}
              {task.tool_call_count > 0 ? ` · 已调用 ${task.tool_call_count} 个工具` : ""}
              {task.iteration_count > 0 ? ` · 第 ${task.iteration_count} 轮规划` : ""}
            </p>
          ) : null}
        </DialogHeader>

        <div className="max-h-[calc(85vh-5rem)] space-y-4 overflow-y-auto px-6 py-4">
          {stuckQueued && (
            <div className="rounded-2xl border border-amber-200/80 bg-amber-50/80 p-3 text-xs text-amber-900">
              任务仍在排队。本地开发会自动在约 3 秒后内联执行；若仍无进展，请确认 Redis 可用，或手动启动{" "}
              <code className="rounded bg-white/80 px-1">python -m arq app.workers.agent_worker.WorkerSettings</code>
            </div>
          )}

          {speechAudio && (
            <section>
              <h4 className="mb-2 text-xs font-bold uppercase tracking-wide text-outline">语音讲解</h4>
              <div className="rounded-2xl bg-white/60 p-4">
                <InlineAudioPlayer audio={speechAudio} />
              </div>
            </section>
          )}

          {decisionSummary && (
            <section>
              <h4 className="mb-2 text-xs font-bold uppercase tracking-wide text-outline">决策摘要</h4>
              <p className="rounded-2xl bg-white/50 p-3 text-sm text-on-surface">{decisionSummary}</p>
            </section>
          )}

          <section>
            <h4 className="mb-2 text-xs font-bold uppercase tracking-wide text-outline">执行过程</h4>
            <div className="space-y-1 rounded-2xl bg-white/50 p-3">
              {events.length > 0 ? (
                events.map((evt, index) => (
                  <AgentEventDetail key={`${evt.type}-${index}`} event={evt} index={index} />
                ))
              ) : (
                <p className="text-xs text-outline">
                  {streaming ? "等待首个事件…" : "暂无执行记录"}
                </p>
              )}
              {streaming && events.length > 0 && (
                <p className="border-t border-white/60 pt-2 text-[11px] text-primary animate-pulse">
                  实时更新中…
                </p>
              )}
            </div>
          </section>

          {waiting && onApprove && (
            <div className="flex gap-2">
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

          {content ? (
            <section>
              <h4 className="mb-2 text-xs font-bold uppercase tracking-wide text-outline">回答内容</h4>
              <div className="rounded-2xl bg-white/60 p-4">
                <MarkdownRenderer content={content} />
              </div>
            </section>
          ) : streaming ? (
            <p className="text-sm text-outline animate-pulse">回答生成中…</p>
          ) : null}

          {artifacts.length > 0 && (
            <section>
              <h4 className="mb-2 text-xs font-bold uppercase tracking-wide text-outline">生成产物</h4>
              <div className="flex flex-wrap gap-2">
                {artifacts.map((ref, i) => (
                  <ArtifactCard key={String(ref.asset_id || ref.resource_id || i)} artifact={ref} />
                ))}
              </div>
            </section>
          )}

          {citations.length > 0 && (
            <section className="text-xs text-outline">
              <h4 className="mb-2 font-bold uppercase tracking-wide">引用来源</h4>
              <ul className="space-y-1">
                {citations.slice(0, 8).map((c, i) => (
                  <li key={i}>{String(c.title || c.source_title || "课程资料")}</li>
                ))}
              </ul>
            </section>
          )}

          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          {task?.error_message && !error ? (
            <p className="text-sm text-destructive">{task.error_message}</p>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  )
}
