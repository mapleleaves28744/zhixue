import { request } from "@/lib/request"
import type { PageData } from "@/types/api"
import type {
  GenerateFromMaterialResponse,
  WikiPage,
  WikiPageListItem,
  WikiPageVersion,
} from "@/types/wiki"

export function listWikiPages(
  courseId: string,
  page = 1,
  pageSize = 20,
): Promise<PageData<WikiPageListItem>> {
  const params = new URLSearchParams({
    course_id: courseId,
    page: String(page),
    page_size: String(pageSize),
  })
  return request<PageData<WikiPageListItem>>(`/api/v1/wiki/pages?${params}`)
}

export function getWikiPage(id: string): Promise<WikiPage> {
  return request<WikiPage>(`/api/v1/wiki/pages/${id}`)
}

export function createWikiPage(data: {
  courseId: string
  title: string
  content: string
  summary?: string
}): Promise<{ id: string; title: string; slug: string; current_version: number }> {
  return request("/api/v1/wiki/pages", {
    method: "POST",
    body: {
      course_id: data.courseId,
      title: data.title,
      content: data.content,
      summary: data.summary ?? null,
    },
  })
}

export function updateWikiPage(
  id: string,
  data: {
    title?: string
    content?: string
    summary?: string
    changeMessage?: string
  },
): Promise<{ id: string; title: string; current_version: number; updated_at: string }> {
  return request(`/api/v1/wiki/pages/${id}`, {
    method: "PUT",
    body: {
      title: data.title ?? null,
      content: data.content ?? null,
      summary: data.summary ?? null,
      change_message: data.changeMessage ?? null,
    },
  })
}

export function archiveWikiPage(id: string): Promise<{ archived: boolean }> {
  return request(`/api/v1/wiki/pages/${id}`, { method: "DELETE" })
}

export function listWikiVersions(pageId: string): Promise<WikiPageVersion[]> {
  return request<WikiPageVersion[]>(`/api/v1/wiki/pages/${pageId}/versions`)
}

export function getWikiVersion(
  pageId: string,
  versionNumber: number,
): Promise<WikiPageVersion> {
  return request<WikiPageVersion>(
    `/api/v1/wiki/pages/${pageId}/versions/${versionNumber}`,
  )
}

export function rollbackWikiVersion(
  pageId: string,
  versionNumber: number,
): Promise<{ id: string; title: string; current_version: number; updated_at: string }> {
  return request(`/api/v1/wiki/pages/${pageId}/rollback/${versionNumber}`, {
    method: "POST",
  })
}

export function generateFromMaterial(
  courseId: string,
  materialId: string,
): Promise<GenerateFromMaterialResponse> {
  return request("/api/v1/wiki/pages/generate-from-material", {
    method: "POST",
    body: { course_id: courseId, material_id: materialId },
  })
}

export function updateFromNote(
  pageId: string,
  noteContent: string,
): Promise<{ id: string; title: string; current_version: number; updated_at: string }> {
  return request("/api/v1/wiki/pages/update-from-note", {
    method: "POST",
    body: { page_id: pageId, note_content: noteContent },
  })
}

export function summarizePage(
  id: string,
): Promise<{ id: string; title: string; summary: string; current_version: number; updated_at: string }> {
  return request(`/api/v1/wiki/pages/${id}/summarize`, { method: "POST" })
}

export function getWikiGraph(courseId: string): Promise<{
  nodes: { id: string; title: string; summary: string | null; current_version: number }[]
  links: { id: string; source_page_id: string; target_page_id: string; relation_type: string }[]
}> {
  return request(`/api/v1/wiki/graph?course_id=${encodeURIComponent(courseId)}`)
}
