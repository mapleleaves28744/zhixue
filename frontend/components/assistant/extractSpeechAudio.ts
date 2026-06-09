import { formatFromMime, normalizeAudioMime } from "@/lib/media"
import type { AgentTask, AgentTaskEvent } from "@/types/agent"

export interface SpeechAudioPayload {
  assetId?: string
  base64?: string
  format?: string
  mimeType?: string
  title?: string
}

function payloadFromRecord(record: Record<string, unknown>, title?: string): SpeechAudioPayload | null {
  const assetId = record.asset_id ? String(record.asset_id) : record.media_asset_id ? String(record.media_asset_id) : ""
  const mimeType = record.mime_type ? String(record.mime_type) : record.media_mime_type ? String(record.media_mime_type) : undefined
  const format = record.format ? String(record.format) : formatFromMime(mimeType)

  if (assetId) {
    return {
      assetId,
      format,
      mimeType: normalizeAudioMime(format, mimeType),
      title: title || String(record.title || "语音讲解"),
    }
  }

  if (typeof record.audio_base64 === "string" && record.audio_base64) {
    return {
      base64: record.audio_base64,
      format,
      mimeType: normalizeAudioMime(format, mimeType),
      assetId: undefined,
      title: title || "语音讲解",
    }
  }

  return null
}

function findExplanationAudio(events: AgentTaskEvent[]): SpeechAudioPayload | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const evt = events[i]
    if (evt.type !== "observation") continue
    if (String(evt.data.tool_name || "") !== "generate_explanation") continue
    const output = evt.data.output
    if (!output || typeof output !== "object") continue
    const payload = payloadFromRecord(output as Record<string, unknown>)
    if (payload) return payload
  }
  return null
}

function findSynthesizeSpeech(events: AgentTaskEvent[]): SpeechAudioPayload | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const evt = events[i]
    if (evt.type !== "observation") continue
    if (String(evt.data.tool_name || "") !== "synthesize_speech") continue
    const output = evt.data.output
    if (!output || typeof output !== "object") continue
    const payload = payloadFromRecord(output as Record<string, unknown>)
    if (payload) return payload
  }
  return null
}

function findAudioFromArtifactRefs(task?: AgentTask | null): SpeechAudioPayload | null {
  const refs = (task?.plan_json?.artifact_refs as Record<string, unknown>[]) || []
  for (let i = refs.length - 1; i >= 0; i--) {
    const ref = refs[i]
    const assetId = ref.asset_id ? String(ref.asset_id) : ""
    if (!assetId) continue
    const refType = String(ref.type || ref.artifact_type || "")
    const mime = String(ref.mime_type || "")
    if (refType === "audio" || mime.startsWith("audio/")) {
      return {
        assetId,
        format: formatFromMime(mime),
        mimeType: normalizeAudioMime(undefined, mime),
        title: String(ref.title || "语音讲解"),
      }
    }
  }
  return null
}

export function extractSpeechAudio(
  events: AgentTaskEvent[],
  task?: AgentTask | null,
): SpeechAudioPayload | null {
  const explanation = findExplanationAudio(events)
  if (explanation) return explanation

  const synthesize = findSynthesizeSpeech(events)
  if (synthesize) {
    if (synthesize.assetId) {
      return {
        ...synthesize,
        base64: undefined,
        mimeType: normalizeAudioMime(synthesize.format, synthesize.mimeType),
      }
    }
    return synthesize
  }

  return findAudioFromArtifactRefs(task)
}
