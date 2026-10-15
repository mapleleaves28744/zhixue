import { request } from "@/lib/request"
import type { PageData } from "@/types/api"
import type {
  GeneratedResource,
  GeneratedResourceListItem,
  ResourceGeneratePayload,
  ResourceGenerateResult,
} from "@/types/resource"

export function generateResource(
  payload: ResourceGeneratePayload,
): Promise<ResourceGenerateResult> {
  return request("/api/v1/resources/generate", {
    method: "POST",
    body: payload,
  })
}

export function listResources(params: {
  courseId?: string
  resourceType?: string
  status?: string
  page?: number
  pageSize?: number
} = {}): Promise<PageData<GeneratedResourceListItem>> {
  const query = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.pageSize ?? 20),
    status: params.status ?? "active",
  })
  if (params.courseId) {
    query.set("course_id", params.courseId)
  }
  if (params.resourceType) {
    query.set("resource_type", params.resourceType)
  }
  return request(`/api/v1/resources?${query}`)
}

export function getResource(id: string): Promise<GeneratedResource> {
  return request(`/api/v1/resources/${id}`)
}

const inlineResourceCache = new Map<string, { expiresAt: number; promise: Promise<GeneratedResource> }>()

export function getInlineResource(id: string): Promise<GeneratedResource> {
  const now = Date.now()
  for (const [cachedId, entry] of inlineResourceCache) {
    if (entry.expiresAt <= now) inlineResourceCache.delete(cachedId)
  }
  const cached = inlineResourceCache.get(id)
  if (cached && cached.expiresAt > now) return cached.promise

  const promise = getResource(id)
  const entry = { expiresAt: now + 10_000, promise }
  inlineResourceCache.set(id, entry)
  void promise.catch(() => {
    if (inlineResourceCache.get(id) === entry) inlineResourceCache.delete(id)
  })
  return promise
}

export function archiveResource(id: string): Promise<GeneratedResource> {
  return request(`/api/v1/resources/${id}`, { method: "DELETE" })
}

export function saveResourceToWiki(
  id: string,
  payload: { wiki_page_id?: string | null; section_title?: string | null },
): Promise<{
  resource: GeneratedResource
  wiki_page: { id: string; title: string; current_version: number }
}> {
  return request(`/api/v1/resources/${id}/save-to-wiki`, {
    method: "POST",
    body: payload,
  })
}
