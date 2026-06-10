"use client"

import { useMemo, useState } from "react"
import { buildApiUrl } from "@/lib/api"
import { getToken } from "@/lib/auth"
import { normalizeAudioMime } from "@/lib/media"
import type { SpeechAudioPayload } from "./extractSpeechAudio"

interface InlineAudioPlayerProps {
  audio: SpeechAudioPayload
  className?: string
}

function buildAssetUrl(assetId: string): string {
  const url = buildApiUrl(`/api/v1/media-assets/${assetId}/file`)
  const token = getToken()
  return token ? `${url}?access_token=${encodeURIComponent(token)}` : url
}

export function InlineAudioPlayer({ audio, className }: InlineAudioPlayerProps) {
  const [useAssetFallback, setUseAssetFallback] = useState(false)

  const mime = normalizeAudioMime(audio.format, audio.mimeType)
  const assetSrc = audio.assetId ? buildAssetUrl(audio.assetId) : ""
  const base64Src = audio.base64 ? `data:${mime};base64,${audio.base64}` : ""

  const src = useMemo(() => {
    if (audio.assetId && (!audio.base64 || useAssetFallback)) return assetSrc
    if (base64Src) return base64Src
    return assetSrc
  }, [assetSrc, audio.assetId, audio.base64, base64Src, useAssetFallback])

  if (!src) return null

  return (
    <div className={className}>
      <div className="mb-2 flex items-center gap-2 text-xs font-bold text-primary">
        <span className="material-symbols-outlined text-base">graphic_eq</span>
        {audio.title || "语音讲解"}
      </div>
      <audio
        controls
        preload="metadata"
        className="w-full max-w-md"
        src={src}
        onError={() => {
          if (audio.assetId && !useAssetFallback) {
            setUseAssetFallback(true)
          }
        }}
      />
    </div>
  )
}
