import { request } from "@/lib/request"
import type { PageData } from "@/types/api"
import type { LearningPath, LearningPathGeneratePayload, LearningPathItem } from "@/types/learning-path"

export function listLearningPaths(params?: {
  courseId?: string
  status?: string
  page?: number
  pageSize?: number
}): Promise<PageData<LearningPath>> {
  const searchParams = new URLSearchParams()
  if (params?.courseId) searchParams.set("course_id", params.courseId)
  if (params?.status) searchParams.set("status", params.status)
  searchParams.set("page", String(params?.page ?? 1))
  searchParams.set("page_size", String(params?.pageSize ?? 5))
  return request<PageData<LearningPath>>(`/api/v1/learning-paths?${searchParams.toString()}`)
}

export function getLearningPath(pathId: string): Promise<LearningPath> {
  return request<LearningPath>(`/api/v1/learning-paths/${pathId}`)
}

export function generateLearningPath(payload: LearningPathGeneratePayload): Promise<LearningPath> {
  return request<LearningPath>("/api/v1/learning-paths/generate", {
    method: "POST",
    body: payload,
  })
}

export function updateLearningPathItem(
  itemId: string,
  status: "pending" | "doing" | "completed" | "skipped",
): Promise<LearningPathItem> {
  return request<LearningPathItem>(`/api/v1/learning-paths/items/${itemId}`, {
    method: "PATCH",
    body: { status },
  })
}

export function archiveLearningPath(pathId: string): Promise<LearningPath> {
  return request<LearningPath>(`/api/v1/learning-paths/${pathId}`, {
    method: "DELETE",
  })
}
