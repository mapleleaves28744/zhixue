import type { AgentTask, AgentTaskEvent } from "@/types/agent"

export interface ChatArtifactRef {
  type: string
  subtype?: string
  id: string
  title?: string
}

export interface ChatMediaArtifactRef {
  type: "audio" | "media_asset"
  id: string
  title?: string
  mimeType?: string
  subtype?: string
  scenesCount?: number
  citationCount?: number
  personalizedReason?: string
}

const TERMINAL_MEDIA_STAGES = new Set([
  "completed",
  "failed",
  "cancelled",
  "video_export_failed",
  "video_export_queue_failed",
])

function artifactRefsFromEvent(event: AgentTaskEvent): unknown[] {
  if (event.type === "tool_completed" && Array.isArray(event.data.artifact_refs)) {
    return event.data.artifact_refs
  }
  if (event.type === "completed" && Array.isArray(event.data.artifacts)) {
    return event.data.artifacts
  }
  if (event.type === "multimodal_progress" && Array.isArray(event.data.artifact_refs)) {
    return event.data.artifact_refs
  }
  return []
}

export function hasMediaJob(events: AgentTaskEvent[]): boolean {
  return events.some((event) =>
    artifactRefsFromEvent(event).some((raw) => {
      if (!raw || typeof raw !== "object") return false
      const item = raw as Record<string, unknown>
      return String(item.type || item.artifact_type || "") === "media_job"
    }),
  )
}

export function hasPendingMediaJobs(events: AgentTaskEvent[]): boolean {
  return extractMediaJobProgress(events).length > 0
}

export interface MediaJobProgressRef {
  jobId: string
  stage: string
  progress: number
  message: string
  subtype?: string
}

export function extractMediaJobProgress(events: AgentTaskEvent[]): MediaJobProgressRef[] {
  const subtypes = new Map<string, string>()
  const latest = new Map<string, MediaJobProgressRef>()

  for (const event of events) {
    for (const raw of artifactRefsFromEvent(event)) {
      if (!raw || typeof raw !== "object") continue
      const item = raw as Record<string, unknown>
      if (String(item.type || item.artifact_type || "") !== "media_job") continue
      const jobId = String(item.job_id || item.id || "")
      if (!jobId) continue
      if (item.subtype) subtypes.set(jobId, String(item.subtype))
    }

    if (event.type === "multimodal_progress") {
      const jobId = String(event.data.job_id || "")
      if (!jobId) continue
      const stage = String(event.data.stage || "")
      latest.set(jobId, {
        jobId,
        stage,
        progress: Number(event.data.progress ?? 0),
        message: String(event.data.message || "后台生成中"),
        subtype: subtypes.get(jobId),
      })
    }
  }

  return [...latest.values()].filter((job) => !TERMINAL_MEDIA_STAGES.has(job.stage))
}

function pushResourceRef(raw: unknown, seen: Set<string>, refs: ChatArtifactRef[]): void {
  if (!raw || typeof raw !== "object") return
  const item = raw as Record<string, unknown>
  const type = String(item.type || item.artifact_type || "")
  if (type !== "resource") return
  const id = String(item.id || item.resource_id || "")
  if (!id || seen.has(`resource:${id}`)) return
  seen.add(`resource:${id}`)
  refs.push({
    type,
    subtype: item.subtype ? String(item.subtype) : undefined,
    id,
    title: item.title ? String(item.title) : undefined,
  })
}

function pushMediaRef(raw: unknown, seen: Set<string>, refs: ChatMediaArtifactRef[]): void {
  if (!raw || typeof raw !== "object") return
  const item = raw as Record<string, unknown>
  const type = String(item.type || item.artifact_type || "")
  if (type !== "audio" && type !== "media_asset") return

  const id = String(item.asset_id || item.id || "")
  if (!id || seen.has(`media:${id}`)) return
  seen.add(`media:${id}`)

  refs.push({
    type: type as "audio" | "media_asset",
    id,
    title: item.title ? String(item.title) : undefined,
    mimeType: item.mime_type ? String(item.mime_type) : undefined,
    subtype: item.subtype ? String(item.subtype) : undefined,
    scenesCount: item.scenes_count != null ? Number(item.scenes_count) : undefined,
    citationCount: item.citation_count != null ? Number(item.citation_count) : undefined,
    personalizedReason: item.personalized_reason ? String(item.personalized_reason) : undefined,
  })
}

function collectFromRefs(
  rawRefs: unknown[],
  seenResource: Set<string>,
  seenMedia: Set<string>,
  resourceRefs: ChatArtifactRef[],
  mediaRefs: ChatMediaArtifactRef[],
): void {
  rawRefs.forEach((ref) => {
    pushResourceRef(ref, seenResource, resourceRefs)
    pushMediaRef(ref, seenMedia, mediaRefs)
  })
}

export function extractChatArtifacts(
  events: AgentTaskEvent[],
  task?: AgentTask | null,
  payloadArtifacts?: Record<string, unknown>[],
): ChatArtifactRef[] {
  const seen = new Set<string>()
  const refs: ChatArtifactRef[] = []

  for (const evt of events) {
    if (evt.type === "tool_completed" && evt.data.success !== false) {
      const artifactRefs = evt.data.artifact_refs
      if (Array.isArray(artifactRefs)) {
        artifactRefs.forEach((ref) => pushResourceRef(ref, seen, refs))
      }
    }
    if (evt.type === "completed") {
      const artifacts = evt.data.artifacts
      if (Array.isArray(artifacts)) {
        artifacts.forEach((ref) => pushResourceRef(ref, seen, refs))
      }
    }
  }

  const planRefs = (task?.plan_json?.artifact_refs as unknown[]) || []
  planRefs.forEach((ref) => pushResourceRef(ref, seen, refs))

  if (payloadArtifacts?.length) {
    payloadArtifacts.forEach((ref) => pushResourceRef(ref, seen, refs))
  }

  return refs
}

export function extractChatMediaArtifacts(
  events: AgentTaskEvent[],
  task?: AgentTask | null,
  payloadArtifacts?: Record<string, unknown>[],
): ChatMediaArtifactRef[] {
  const seenResource = new Set<string>()
  const seenMedia = new Set<string>()
  const resourceRefs: ChatArtifactRef[] = []
  const mediaRefs: ChatMediaArtifactRef[] = []

  for (const evt of events) {
    if (evt.type === "tool_completed" && evt.data.success !== false) {
      const artifactRefs = evt.data.artifact_refs
      if (Array.isArray(artifactRefs)) {
        collectFromRefs(artifactRefs, seenResource, seenMedia, resourceRefs, mediaRefs)
      }
    }
    if (evt.type === "completed") {
      const artifacts = evt.data.artifacts
      if (Array.isArray(artifacts)) {
        collectFromRefs(artifacts, seenResource, seenMedia, resourceRefs, mediaRefs)
      }
    }
    if (evt.type === "multimodal_progress") {
      const artifactRefs = evt.data.artifact_refs
      if (Array.isArray(artifactRefs)) {
        collectFromRefs(artifactRefs, seenResource, seenMedia, resourceRefs, mediaRefs)
      }
    }
  }

  const planRefs = (task?.plan_json?.artifact_refs as unknown[]) || []
  collectFromRefs(planRefs, seenResource, seenMedia, resourceRefs, mediaRefs)

  if (payloadArtifacts?.length) {
    collectFromRefs(payloadArtifacts, seenResource, seenMedia, resourceRefs, mediaRefs)
  }

  if (resourceRefs.length > 0) {
    return mediaRefs.filter((ref) => ref.type !== "audio")
  }

  return mediaRefs
}
