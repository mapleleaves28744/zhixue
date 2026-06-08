import type { AgentTask, AgentTaskEvent } from "@/types/agent"

export interface SpeechAudioPayload {
  assetId?: string
  base64?: string
  format?: string
  title?: string
}

export function extractSpeechAudio(
  events: AgentTaskEvent[],
  task?: AgentTask | null,
): SpeechAudioPayload | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const evt = events[i]
    if (evt.type !== "observation") continue
    const toolName = String(evt.data.tool_name || "")
    if (toolName !== "synthesize_speech") continue
    const output = evt.data.output
    if (!output || typeof output !== "object") continue
    const record = output as Record<string, unknown>
    if (typeof record.audio_base64 === "string" && record.audio_base64) {
      return {
        base64: record.audio_base64,
        format: String(record.format || "wav"),
        assetId: record.asset_id ? String(record.asset_id) : undefined,
        title: "语音讲解",
      }
    }
    if (record.asset_id) {
      return {
        assetId: String(record.asset_id),
        format: String(record.format || "wav"),
        title: "语音讲解",
      }
    }
  }

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
        format: mime.includes("wav") ? "wav" : "wav",
        title: String(ref.title || "语音讲解"),
      }
    }
  }
  return null
}
