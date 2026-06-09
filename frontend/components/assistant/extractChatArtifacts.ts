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
}

function pushResourceRef(
  raw: unknown,
  seen: Set<string>,
  refs: ChatArtifactRef[],
): void {
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

function pushMediaRef(
  raw: unknown,
  seen: Set<string>,
  refs: ChatMediaArtifactRef[],
): void {
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
