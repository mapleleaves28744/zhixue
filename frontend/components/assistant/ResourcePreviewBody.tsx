"use client"

import { useEffect, useState } from "react"
import { MermaidDiagram } from "@/components/assistant/MermaidDiagram"
import { MediaAssetPreview } from "@/components/assistant/MediaAssetPreview"
import { MarkdownRenderer } from "@/components/markdown/MarkdownRenderer"
import { buildApiUrl } from "@/lib/api"
import { getToken } from "@/lib/auth"
import { getResourcePreviewMode } from "@/lib/mermaid"
import { getMediaJob } from "@/services/multimodalService"
import { getResource } from "@/services/resourceService"
import type { GeneratedResource } from "@/types/resource"

interface ResourcePreviewBodyProps {
  resource: GeneratedResource
  showPersonalizedReason?: boolean
  collapseScript?: boolean
  mediaJobId?: string | null
  onResourceUpdated?: (resource: GeneratedResource) => void
}

function ImmersiveClassroomLaunch({ assetId, title }: { assetId: string; title: string }) {
  const token = getToken()
  const launchUrl = buildApiUrl(`/api/v1/media-assets/${assetId}/launch`)
  const href = token ? `${launchUrl}?access_token=${encodeURIComponent(token)}` : launchUrl

  return (
    <div className="overflow-hidden rounded-2xl border border-indigo-200/70 bg-gradient-to-br from-white via-indigo-50/70 to-cyan-50/70 p-5">
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-indigo-500">OpenMAIC 沉浸课堂</p>
      <h3 className="mt-2 text-lg font-bold text-slate-900">{title}</h3>
      <a
        href={href}
        target="_blank"
        rel="noreferrer"
        className="mt-4 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-500 px-4 py-2 text-sm font-bold text-white"
      >
        <span className="material-symbols-outlined text-lg">play_circle</span>
        进入沉浸课堂
      </a>
    </div>
  )
}

function MediaJobProgress({
  jobId,
  message,
  resourceId,
  onDone,
}: {
  jobId: string
  message?: string | null
  resourceId: string
  onDone: (resource: GeneratedResource) => void
}) {
  const [progress, setProgress] = useState(0)
  const [stage, setStage] = useState("queued")
  const [statusMessage, setStatusMessage] = useState(message || "后台生成中…")

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined

    const poll = async () => {
      try {
        const job = await getMediaJob(jobId)
        if (cancelled) return
        setProgress(job.progress ?? 0)
        setStage(job.stage || job.status)
        if (job.error_message) setStatusMessage(job.error_message)
        else if (job.stage) setStatusMessage(`正在${job.stage}…`)

        if (job.status === "succeeded") {
          const refreshed = await getResource(resourceId)
          if (!cancelled) onDone(refreshed)
          return
        }
        if (job.status === "failed") return
        timer = setTimeout(poll, 3000)
      } catch {
        if (!cancelled) timer = setTimeout(poll, 5000)
      }
    }

    void poll()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [jobId, resourceId, onDone])

  return (
    <div className="rounded-2xl border border-amber-200/60 bg-gradient-to-br from-white via-amber-50/40 to-orange-50/30 p-4">
      <p className="text-sm font-semibold text-on-surface">{statusMessage}</p>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-amber-100">
        <div
          className="h-full rounded-full bg-gradient-to-r from-amber-500 to-orange-500 transition-all"
          style={{ width: `${Math.max(5, progress)}%` }}
        />
      </div>
      <p className="mt-2 text-xs text-outline">
        {stage} · {progress}%
      </p>
    </div>
  )
}

export function ResourcePreviewBody({
  resource,
  showPersonalizedReason = false,
  collapseScript = false,
  mediaJobId = null,
  onResourceUpdated,
}: ResourcePreviewBodyProps) {
  const [liveResource, setLiveResource] = useState(resource)
  const previewMode = getResourcePreviewMode(liveResource)
  const hasMedia = Boolean(liveResource.media_asset_id)
  const pendingJob = mediaJobId && !hasMedia

  useEffect(() => {
    setLiveResource(resource)
  }, [resource])

  const handleJobDone = (updated: GeneratedResource) => {
    setLiveResource(updated)
    onResourceUpdated?.(updated)
  }

  return (
    <>
      {pendingJob ? (
        <MediaJobProgress
          jobId={mediaJobId}
          message={null}
          resourceId={liveResource.id}
          onDone={handleJobDone}
        />
      ) : null}

      {previewMode === "immersive_classroom" && !hasMedia && !pendingJob ? (
        <div className="rounded-2xl border border-amber-200/60 bg-amber-50/50 p-4 text-sm text-on-surface">
          沉浸课堂仍在生成或未绑定媒体资产，请稍候刷新；若长时间无内容，请重新生成。
        </div>
      ) : null}

      {previewMode === "immersive_classroom" && hasMedia ? (
        <div className="space-y-3">
          <ImmersiveClassroomLaunch assetId={liveResource.media_asset_id!} title={liveResource.title} />
          {liveResource.preview_video_asset_id ? (
            <details className="rounded-2xl border border-white/80 bg-white/60 p-4">
              <summary className="cursor-pointer text-sm font-bold text-primary">课堂讲解视频预览</summary>
              <div className="mt-3">
                <MediaAssetPreview
                  assetId={liveResource.preview_video_asset_id}
                  mimeType={liveResource.preview_video_mime_type || "video/mp4"}
                  title={`${liveResource.title} · 讲解视频`}
                />
              </div>
            </details>
          ) : null}
        </div>
      ) : null}

      {previewMode === "html" && hasMedia ? (
        <div className="space-y-3">
          <MediaAssetPreview
            assetId={liveResource.media_asset_id!}
            mimeType={liveResource.media_mime_type || "text/html"}
            title={liveResource.title}
          />
          <details className="rounded-2xl border border-white/80 bg-white/60 p-4">
            <summary className="cursor-pointer text-sm font-bold text-primary">查看课件说明</summary>
            <div className="mt-3">
              <MarkdownRenderer content={liveResource.content} />
            </div>
          </details>
        </div>
      ) : null}

      {previewMode === "image" && hasMedia ? (
        <MediaAssetPreview
          assetId={liveResource.media_asset_id!}
          mimeType={liveResource.media_mime_type}
          title={liveResource.title}
        />
      ) : null}

      {previewMode === "video" && hasMedia ? (
        <div className="space-y-3">
          <MediaAssetPreview
            assetId={liveResource.media_asset_id!}
            mimeType={liveResource.media_mime_type || "video/mp4"}
            title={liveResource.title}
          />
          <details className="rounded-2xl border border-white/80 bg-white/60 p-4">
            <summary className="cursor-pointer text-sm font-bold text-primary">查看生成说明</summary>
            <div className="mt-3">
              <MarkdownRenderer content={liveResource.content} />
            </div>
          </details>
        </div>
      ) : null}

      {previewMode === "audio" && hasMedia ? (
        <div className="space-y-3">
          <div className="rounded-2xl border border-primary/15 bg-primary/5 p-4">
            <p className="mb-3 flex items-center gap-2 text-sm font-bold text-primary">
              <span className="material-symbols-outlined text-lg">volume_up</span>
              语音讲解
            </p>
            <MediaAssetPreview
              assetId={liveResource.media_asset_id!}
              mimeType={liveResource.media_mime_type || "audio/mpeg"}
              title={liveResource.title}
            />
          </div>
          {collapseScript ? (
            <details className="rounded-2xl border border-white/80 bg-white/60 p-4">
              <summary className="cursor-pointer text-sm font-bold text-primary">展开文字讲稿</summary>
              <div className="mt-3">
                <MarkdownRenderer content={liveResource.content} />
              </div>
            </details>
          ) : (
            <MarkdownRenderer content={liveResource.content} />
          )}
        </div>
      ) : null}

      {previewMode === "mermaid" ? (
        <div className="space-y-3">
          {hasMedia && liveResource.media_mime_type?.startsWith("image/") ? (
            <MediaAssetPreview
              assetId={liveResource.media_asset_id!}
              mimeType={liveResource.media_mime_type}
              title={liveResource.title}
            />
          ) : null}
          <MermaidDiagram code={liveResource.content} title={liveResource.title} />
        </div>
      ) : null}

      {previewMode === "text" && !pendingJob ? <MarkdownRenderer content={liveResource.content} /> : null}

      {showPersonalizedReason && liveResource.personalized_reason ? (
        <details className="mt-4 rounded-xl bg-primary/5 p-3">
          <summary className="cursor-pointer text-sm font-bold text-primary">个性化原因</summary>
          <p className="mt-2 text-sm text-on-surface-variant">{liveResource.personalized_reason}</p>
        </details>
      ) : null}
    </>
  )
}

export function shouldInlineResource(resource: GeneratedResource): boolean {
  const previewMode = getResourcePreviewMode(resource)
  if (previewMode !== "text") return true
  return Boolean(resource.media_asset_id)
}
