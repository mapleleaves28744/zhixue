import { request } from "@/lib/request"
import type { ExtractKnowledgeResponse, KnowledgeSearchResult } from "@/types/knowledge"

export function searchKnowledge(params: {
  courseId: string
  query: string
  topK?: number
  knowledgeId?: string
}): Promise<KnowledgeSearchResult[]> {
  return request<KnowledgeSearchResult[]>("/api/v1/knowledge/search", {
    method: "POST",
    body: {
      course_id: params.courseId,
      query: params.query,
      top_k: params.topK ?? 5,
      knowledge_id: params.knowledgeId ?? null
    }
  })
}

export function extractKnowledgeFromMaterial(materialId: string): Promise<ExtractKnowledgeResponse> {
  return request<ExtractKnowledgeResponse>("/api/v1/knowledge/extract-from-material", {
    method: "POST",
    body: { material_id: materialId }
  })
}
