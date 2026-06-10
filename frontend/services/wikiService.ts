import { request } from "@/lib/request"
import type { PageData } from "@/types/api"

export interface WikiPageSummary {
  id: string
  course_id: string
  title: string
  summary?: string | null
  page_type: string
  status: string
  created_at: string
  updated_at: string
}

export function listWikiPages(courseId: string): Promise<PageData<WikiPageSummary>> {
  const query = new URLSearchParams({
    course_id: courseId,
    page: "1",
    page_size: "50",
  })
  return request<PageData<WikiPageSummary>>(`/api/v1/wiki/pages?${query}`)
}
