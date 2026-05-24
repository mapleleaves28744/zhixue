export interface KnowledgeSearchResult {
  chunk_id: string
  content: string
  score: number
  source_title: string | null
  page_no: number | null
  material_id: string
}

export interface KnowledgePoint {
  id: string
  name: string
  chapter: string | null
  description: string | null
}

export interface ExtractKnowledgeResponse {
  extracted_count: number
  points: KnowledgePoint[]
}
