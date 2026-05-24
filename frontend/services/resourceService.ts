import { request } from "@/lib/request"
import type { PageData } from "@/types/api"
import type {
  GeneratedResource,
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
} = {}): Promise<PageData<GeneratedResource>> {
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
