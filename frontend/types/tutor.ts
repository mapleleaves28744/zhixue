export interface TutorCitation {
  citation_key?: string | null
  source_type: string
  title: string
  source_id?: string | null
  chunk_id?: string | null
  page_id?: string | null
  knowledge_id?: string | null
  page_no?: number | null
  score?: number | null
  quote?: string | null
  retrieval_mode?: string | null
  confidence?: string | null
}

export interface RelatedKnowledgePoint {
  knowledge_id?: string | null
  name: string
}

export interface TutorChatRequest {
  course_id: string
  question: string
  conversation_id?: string | null
  session_id?: string | null
  knowledge_id?: string | null
  wiki_page_id?: string | null
  top_k?: number
  use_rag?: boolean
  use_wiki?: boolean
  use_profile?: boolean
  stream?: boolean
}

export interface TutorPerformance {
  retrieval_ms: number
  first_token_ms?: number | null
  generation_ms: number
  total_ms: number
  llm_call_count: number
  evidence_candidate_count: number
  evidence_accepted_count: number
}

export interface TutorChatResponse {
  answer: string
  citations: TutorCitation[]
  related_knowledge_points: RelatedKnowledgePoint[]
  follow_up_questions: string[]
  save_to_wiki_candidate?: string | null
  agent_run_id?: string | null
  review_result: Record<string, unknown>
  memory_update_suggestion: Record<string, unknown>
  message_id?: string | null
  conversation_id?: string | null
  model?: string | null
  provider?: string | null
  fallback_used: boolean
  failed_provider?: string | null
  fallback_reason?: string | null
  knowledge_extract: Record<string, unknown>
  graph_context: Record<string, unknown>
  grounding_status: "grounded" | "partial" | "insufficient"
  grounding_message: string
  performance: TutorPerformance
  postprocess_status: "queued" | "skipped"
}

export interface TutorSaveToWikiRequest {
  wiki_page_id: string
  section_title?: string | null
}

export interface TutorFeedbackRequest {
  feedback_type: "like" | "dislike" | "useful" | "useless" | "report_error"
  rating?: number | null
  comment?: string | null
}
