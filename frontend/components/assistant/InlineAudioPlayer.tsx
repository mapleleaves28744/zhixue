"use client"

import { buildApiUrl } from "@/lib/api"
import { getToken } from "@/lib/auth"
import type { SpeechAudioPayload } from "./extractSpeechAudio"

interface InlineAudioPlayerProps {
  audio: SpeechAudioPayload
  className?: string
}

export function InlineAudioPlayer({ audio, className }: InlineAudioPlayerProps) {
  const mime = audio.format === "pcm16" ? "audio/wav" : `audio/${audio.format || "wav"}`
  const src = audio.base64
    ? `data:${mime};base64,${audio.base64}`
    : audio.assetId
      ? (() => {
          const url = buildApiUrl(`/api/v1/media-assets/${audio.assetId}/file`)
          const token = getToken()
          return token ? `${url}?access_token=${encodeURIComponent(token)}` : url
        })()
      : ""

  if (!src) return null

  return (
    <div className={className}>
      <div className="mb-2 flex items-center gap-2 text-xs font-bold text-primary">
        <span className="material-symbols-outlined text-base">graphic_eq</span>
        {audio.title || "语音讲解"}
      </div>
      <audio controls preload="metadata" className="w-full max-w-md" src={src} />
    </div>
  )
}
