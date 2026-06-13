import { request } from "@/lib/request"
import type { LearningPathDetail } from "@/types/learningPath"

export function getLearningPath(pathId: string): Promise<LearningPathDetail> {
  return request<LearningPathDetail>(`/learning-paths/${pathId}`)
}
