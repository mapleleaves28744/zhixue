"use client"

import { useEffect, useMemo, useState } from "react"
import { cn } from "@/lib/utils"
import type { AgentTaskEvent } from "@/types/agent"
import { buildAgentStepTimeline, type AgentTimelineStepStatus } from "./agentTimelineSteps"

interface AgentStepTimelineProps {
  events: AgentTaskEvent[]
  streaming: boolean
  onOpenDetail?: () => void
}

const STATUS_STYLES: Record<AgentTimelineStepStatus, string> = {
  running: "border-primary/30 bg-primary/10 text-primary",
  complete: "border-emerald-200 bg-emerald-50 text-emerald-700",
  error: "border-destructive/30 bg-destructive/10 text-destructive",
  waiting: "border-amber-200 bg-amber-50 text-amber-700",
}

const STATUS_ICONS: Record<AgentTimelineStepStatus, string> = {
  running: "progress_activity",
  complete: "check_circle",
  error: "error",
  waiting: "help",
}

function statusLabel(status: AgentTimelineStepStatus): string {
  if (status === "running") return "执行中"
  if (status === "complete") return "已完成"
  if (status === "error") return "失败"
  return "待确认"
}

export function AgentStepTimeline({ events, streaming, onOpenDetail }: AgentStepTimelineProps) {
  const steps = useMemo(() => buildAgentStepTimeline(events, streaming), [events, streaming])
  const [openStepIds, setOpenStepIds] = useState<Set<string>>(() => new Set())

  useEffect(() => {
    setOpenStepIds((prev) => {
      const next = new Set(prev)
      for (const step of steps) {
        if (step.status === "running" || step.status === "waiting") next.add(step.id)
      }
      return next
    })
  }, [steps])

  if (!steps.length) return null

  return (
    <div className="glass-card rounded-3xl rounded-tl-md px-4 py-3 shadow-sm">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-outline">实时执行轨迹</p>
          <p className="mt-0.5 text-[11px] text-on-surface-variant">
            每一行都是智能体的一次思考、工具调用或产物生成
          </p>
        </div>
        {onOpenDetail ? (
          <button
            type="button"
            onClick={onOpenDetail}
            className="shrink-0 rounded-full border border-white/80 bg-white/70 px-3 py-1 text-[11px] font-semibold text-outline transition hover:text-primary"
          >
            完整日志
          </button>
        ) : null}
      </div>

      <div className="space-y-1.5">
        {steps.map((step, index) => {
          const hasDetail = Boolean(step.detailText?.trim())
          return (
            <details
              key={step.id}
              className="group relative pl-7"
              open={openStepIds.has(step.id)}
            >
              {index < steps.length - 1 ? (
                <span className="absolute left-[10px] top-7 h-[calc(100%-0.25rem)] w-px bg-outline/15" />
              ) : null}
              <summary
                onClick={(event) => {
                  if (!hasDetail) return
                  event.preventDefault()
                  setOpenStepIds((prev) => {
                    const next = new Set(prev)
                    if (next.has(step.id)) next.delete(step.id)
                    else next.add(step.id)
                    return next
                  })
                }}
                className={cn(
                  "flex list-none items-start gap-2 rounded-2xl px-2 py-1.5 transition hover:bg-white/55",
                  hasDetail && "cursor-pointer",
                )}
              >
                <span
                  className={cn(
                    "absolute left-0 top-2 flex h-5 w-5 items-center justify-center rounded-full border text-[13px]",
                    STATUS_STYLES[step.status],
                    step.status === "running" && "animate-pulse",
                  )}
                >
                  <span className="material-symbols-outlined text-[14px]">
                    {step.status === "complete" || step.status === "error" ? STATUS_ICONS[step.status] : step.icon}
                  </span>
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-on-surface">{step.title}</span>
                    <span
                      className={cn(
                        "rounded-full border px-2 py-0.5 text-[10px] font-bold",
                        STATUS_STYLES[step.status],
                      )}
                    >
                      {statusLabel(step.status)}
                    </span>
                  </span>
                  {step.subtitle ? (
                    <span className="mt-0.5 block truncate text-xs text-on-surface-variant">{step.subtitle}</span>
                  ) : null}
                </span>
                {hasDetail ? (
                  <span className="material-symbols-outlined mt-0.5 shrink-0 text-[18px] text-outline transition group-open:rotate-180">
                    expand_more
                  </span>
                ) : null}
              </summary>
              {hasDetail ? (
                <pre className="ml-2 mt-1 max-h-72 overflow-auto whitespace-pre-wrap rounded-2xl border border-white/70 bg-white/70 p-3 text-[11px] leading-relaxed text-on-surface-variant">
                  {step.detailText}
                </pre>
              ) : null}
            </details>
          )
        })}
      </div>
    </div>
  )
}
