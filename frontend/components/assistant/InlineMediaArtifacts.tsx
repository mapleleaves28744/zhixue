"use client"

import { MediaAssetPreview } from "@/components/assistant/MediaAssetPreview"
import type { ChatMediaArtifactRef } from "@/components/assistant/extractChatArtifacts"

interface InlineMediaArtifactsProps {
  refs: ChatMediaArtifactRef[]
}

export function InlineMediaArtifacts({ refs }: InlineMediaArtifactsProps) {
  if (!refs.length) return null

  return (
    <div className="flex w-full flex-col gap-3">
      {refs.map((ref) => (
        <div key={ref.id} className="glass-card rounded-3xl rounded-tl-md p-4 shadow-sm">
          <p className="mb-3 flex items-center gap-2 text-sm font-bold text-primary">
            <span className="material-symbols-outlined text-lg">
              {ref.mimeType?.startsWith("video/") ? "movie" : ref.mimeType?.startsWith("image/") ? "image" : "graphic_eq"}
            </span>
            {ref.title || (ref.type === "audio" ? "语音讲解" : "媒体产物")}
          </p>
          <MediaAssetPreview assetId={ref.id} mimeType={ref.mimeType} title={ref.title} />
        </div>
      ))}
    </div>
  )
}
