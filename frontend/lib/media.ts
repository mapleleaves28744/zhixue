export function normalizeAudioMime(format?: string | null, mimeType?: string | null): string {
  const mime = String(mimeType || "").trim().toLowerCase()
  if (mime.startsWith("audio/")) {
    if (mime === "audio/mp3") return "audio/mpeg"
    return mime
  }

  const fmt = String(format || "").trim().toLowerCase()
  if (fmt === "mp3" || fmt === "mpeg") return "audio/mpeg"
  if (fmt === "pcm16" || fmt === "wav") return "audio/wav"
  if (fmt === "ogg") return "audio/ogg"
  return "audio/wav"
}

export function formatFromMime(mimeType?: string | null): string {
  const mime = String(mimeType || "").toLowerCase()
  if (mime.includes("mpeg") || mime.includes("mp3")) return "mp3"
  if (mime.includes("ogg")) return "ogg"
  return "wav"
}
