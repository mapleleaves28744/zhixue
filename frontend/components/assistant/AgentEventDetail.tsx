"use client"

import type { ReactNode } from "react"
import { MarkdownRenderer } from "@/components/markdown/MarkdownRenderer"
import { normalizeAgentAnswer } from "@/lib/normalizeAgentAnswer"
import { buildApiUrl } from "@/lib/api"
import { getToken } from "@/lib/auth"
import { normalizeAudioMime } from "@/lib/media"
import type { AgentTaskEvent } from "@/types/agent"
import { eventLabel } from "./streamLabels"

function JsonBlock({ value }: { value: unknown }) {
  const text =
    typeof value === "string" ? value : JSON.stringify(value, null, 2)
  return (
    <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-white/70 p-2 text-[11px] text-on-surface-variant">
      {text}
    </pre>
  )
}

function AudioPreview({
  base64,
  format,
  assetId,
  mimeType,
}: {
  base64?: string
  format?: string
  assetId?: string
  mimeType?: string
}) {
  if (assetId) {
    const url = buildApiUrl(`/api/v1/media-assets/${assetId}/file`)
    const token = getToken()
    const assetSrc = token ? `${url}?access_token=${encodeURIComponent(token)}` : url
    return <audio controls className="mt-2 w-full max-w-md" src={assetSrc} />
  }
  if (!base64) return null
  const mime = normalizeAudioMime(format, mimeType)
  return <audio controls className="mt-2 w-full max-w-md" src={`data:${mime};base64,${base64}`} />
}

function summarizeOutput(output: unknown, toolName?: string): ReactNode {
  if (output == null) return null
  if (typeof output !== "object") {
    return <p className="mt-1 whitespace-pre-wrap text-on-surface-variant">{String(output)}</p>
  }
  const record = output as Record<string, unknown>
  const assetId = record.asset_id ? String(record.asset_id) : record.media_asset_id ? String(record.media_asset_id) : undefined
  if (assetId || (record.audio_base64 && typeof record.audio_base64 === "string")) {
    return (
      <div className="mt-1 space-y-1">
        <p className="text-on-surface-variant">
          语音已生成 · {String(record.provider || "provider")} / {String(record.model || "model")}
          {record.text_length != null ? ` · ${record.text_length} 字` : ""}
        </p>
        <AudioPreview
          base64={typeof record.audio_base64 === "string" ? record.audio_base64 : undefined}
          format={String(record.format || "wav")}
          assetId={assetId}
          mimeType={String(record.mime_type || record.media_mime_type || "")}
        />
      </div>
    )
  }
  if (toolName === "synthesize_speech" && record.error_message) {
    return <p className="mt-1 text-destructive">{String(record.error_message)}</p>
  }
  const { audio_base64: _a, ...rest } = record
  if (Object.keys(rest).length === 0) return null
  return <JsonBlock value={rest} />
}

interface AgentEventDetailProps {
  event: AgentTaskEvent
  index: number
}

export function AgentEventDetail({ event, index }: AgentEventDetailProps) {
  const { type, data } = event
  const toolName = data.tool_name ? String(data.tool_name) : undefined

  return (
    <div className="border-b border-white/60 pb-3 last:border-0">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className="text-[10px] font-bold text-outline">#{index + 1}</span>
        <span className="text-xs font-bold text-primary">{eventLabel(type)}</span>
        {toolName ? (
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">
            {toolName}
          </span>
        ) : null}
      </div>

      {data.message ? (
        <p className="mt-1 text-xs text-on-surface-variant">{String(data.message)}</p>
      ) : null}

      {type === "queued" && data.requeued ? (
        <p className="mt-1 text-[11px] text-outline">已尝试重新入队</p>
      ) : null}

      {(type === "plan_created" || type === "replanned") && (
        <div className="mt-2 space-y-2">
          {data.summary ? (
            <p className="text-xs font-medium text-on-surface">{String(data.summary)}</p>
          ) : null}
          {data.reasoning_content ? (
            <details className="rounded-lg bg-white/60 p-2">
              <summary className="cursor-pointer text-[11px] font-bold text-outline">
                规划思路
              </summary>
              <p className="mt-2 whitespace-pre-wrap text-xs text-on-surface-variant">
                {String(data.reasoning_content)}
              </p>
            </details>
          ) : null}
          {Array.isArray(data.plan) && data.plan.length > 0 && (
            <ol className="list-decimal space-y-1 pl-4 text-xs text-on-surface-variant">
              {(data.plan as string[]).map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
          )}
          {Array.isArray(data.tool_calls) && (data.tool_calls as unknown[]).length > 0 && (
            <details className="rounded-lg bg-white/60 p-2">
              <summary className="cursor-pointer text-[11px] font-bold text-outline">
                工具调用计划 ({(data.tool_calls as unknown[]).length})
              </summary>
              <JsonBlock value={data.tool_calls} />
            </details>
          )}
        </div>
      )}

      {type === "tool_started" && data.arguments != null && (
        <details className="mt-2 rounded-lg bg-white/60 p-2" open>
          <summary className="cursor-pointer text-[11px] font-bold text-outline">输入参数</summary>
          <JsonBlock value={data.arguments} />
        </details>
      )}

      {type === "tool_completed" && (
        <div className="mt-1 space-y-1 text-xs">
          <p className={data.success === false ? "text-destructive" : "text-emerald-700"}>
            {data.success === false
              ? `失败：${String(data.error_message || "未知错误")}`
              : "执行成功"}
            {data.attempts != null ? ` · 尝试 ${String(data.attempts)} 次` : ""}
          </p>
          {Array.isArray(data.artifact_refs) && (data.artifact_refs as unknown[]).length > 0 && (
            <p className="text-outline">
              产物：{(data.artifact_refs as Record<string, unknown>[])
                .map((a) => String(a.type || a.artifact_type || "artifact"))
                .join("、")}
            </p>
          )}
        </div>
      )}

      {type === "observation" && (
        <div className="mt-1">
          {Array.isArray(data.evidence) && data.evidence.length > 0 && (
            <ul className="mb-2 list-disc pl-4 text-[11px] text-outline">
              {(data.evidence as unknown[]).slice(0, 5).map((item, i) => (
                <li key={i}>{typeof item === "string" ? item : JSON.stringify(item)}</li>
              ))}
            </ul>
          )}
          {summarizeOutput(data.output, toolName || String(data.tool_name || ""))}
        </div>
      )}

      {type === "reviewed" && data.issues != null && (
        <JsonBlock value={data} />
      )}

      {type === "completed" && data.final_answer ? (
        <div className="mt-1 max-h-40 overflow-hidden text-xs">
          <MarkdownRenderer content={normalizeAgentAnswer(String(data.final_answer))} />
        </div>
      ) : null}

      {type === "failed" && (
        <p className="mt-1 text-xs text-destructive">
          {String(data.error_message || "任务失败")}
        </p>
      )}

      {type === "waiting_confirmation" && (
        <JsonBlock value={data.arguments || data} />
      )}

      {type === "multimodal_progress" && data.stage ? (
        <p className="mt-1 text-xs text-on-surface-variant">
          阶段：{String(data.stage)}
          {data.progress != null ? ` · ${String(data.progress)}%` : ""}
        </p>
      ) : null}
    </div>
  )
}

const TASK_STATUS_LABELS: Record<string, string> = {
  queued: "排队中",
  running: "执行中",
  waiting_confirmation: "等待确认",
  succeeded: "已完成",
  failed: "失败",
  cancelled: "已取消",
  planned: "已规划",
  draft: "草稿",
}

export function taskStatusLabel(status?: string): string {
  if (!status) return "未知"
  return TASK_STATUS_LABELS[status] || status
}
