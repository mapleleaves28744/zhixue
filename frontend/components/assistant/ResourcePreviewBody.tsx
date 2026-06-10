"use client"

import { MermaidDiagram } from "@/components/assistant/MermaidDiagram"
import { MediaAssetPreview } from "@/components/assistant/MediaAssetPreview"
import { MarkdownRenderer } from "@/components/markdown/MarkdownRenderer"
import { getResourcePreviewMode } from "@/lib/mermaid"
import type { GeneratedResource } from "@/types/resource"

interface ResourcePreviewBodyProps {
  resource: GeneratedResource
  showPersonalizedReason?: boolean
  collapseScript?: boolean
}

export function ResourcePreviewBody({
  resource,
  showPersonalizedReason = false,
  collapseScript = false,
}: ResourcePreviewBodyProps) {
  const previewMode = getResourcePreviewMode(resource)
  const hasMedia = Boolean(resource.media_asset_id)

  return (
    <>
      {previewMode === "image" && hasMedia ? (
        <MediaAssetPreview
          assetId={resource.media_asset_id!}
          mimeType={resource.media_mime_type}
          title={resource.title}
        />
      ) : null}

      {previewMode === "audio" && hasMedia ? (
        <div className="space-y-3">
          <div className="rounded-2xl border border-primary/15 bg-primary/5 p-4">
            <p className="mb-3 flex items-center gap-2 text-sm font-bold text-primary">
              <span className="material-symbols-outlined text-lg">volume_up</span>
              语音讲解
            </p>
            <MediaAssetPreview
              assetId={resource.media_asset_id!}
              mimeType={resource.media_mime_type || "audio/mpeg"}
              title={resource.title}
            />
          </div>
          {collapseScript ? (
            <details className="rounded-2xl border border-white/80 bg-white/60 p-4">
              <summary className="cursor-pointer text-sm font-bold text-primary">展开文字讲稿</summary>
              <div className="mt-3">
                <MarkdownRenderer content={resource.content} />
              </div>
            </details>
          ) : (
            <MarkdownRenderer content={resource.content} />
          )}
        </div>
      ) : null}

      {previewMode === "mermaid" ? (
        <div className="space-y-3">
          {hasMedia && resource.media_mime_type?.startsWith("image/") ? (
            <MediaAssetPreview
              assetId={resource.media_asset_id!}
              mimeType={resource.media_mime_type}
              title={resource.title}
            />
          ) : null}
          <MermaidDiagram code={resource.content} title={resource.title} />
        </div>
      ) : null}

      {previewMode === "text" ? <MarkdownRenderer content={resource.content} /> : null}

      {showPersonalizedReason && resource.personalized_reason ? (
        <details className="mt-4 rounded-xl bg-primary/5 p-3">
          <summary className="cursor-pointer text-sm font-bold text-primary">个性化原因</summary>
          <p className="mt-2 text-sm text-on-surface-variant">{resource.personalized_reason}</p>
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
