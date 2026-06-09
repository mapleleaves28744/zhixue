"use client"

import { buildApiUrl } from "@/lib/api"
import { getToken } from "@/lib/auth"

interface MediaAssetPreviewProps {
  assetId: string
  mimeType?: string | null
  title?: string
}

export function MediaAssetPreview({ assetId, mimeType, title }: MediaAssetPreviewProps) {
  const url = buildApiUrl(`/api/v1/media-assets/${assetId}/file`)
  const token = getToken()
  const src = token ? `${url}?access_token=${encodeURIComponent(token)}` : url
  const mime = mimeType || ""

  if (mime.startsWith("video/")) {
    return <video controls className="max-h-[60vh] w-full rounded-xl" src={src} />
  }
  if (mime.startsWith("audio/")) {
    return <audio controls className="w-full max-w-lg" src={src} />
  }
  if (mime.startsWith("image/") || !mime) {
    return (
      <img
        alt={title || "教学插图"}
        className="max-h-[60vh] w-full rounded-xl object-contain"
        src={src}
      />
    )
  }
  return (
    <iframe
      title={title || "artifact"}
      src={src}
      className="h-[480px] w-full rounded-xl border border-border"
    />
  )
}
