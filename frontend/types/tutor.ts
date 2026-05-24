export interface TutorCitation {
  source_type: string
  title: string
  source_id?: string | null
  chunk_id?: string | null
  page_id?: string | null
  page_no?: number | null
  score?: number | null
  quote?: string | null
}

export interface RelatedKnowledgePoint {
  knowledge_id?: string | null
  name: string
}

export interface TutorChatRequest {
  course_id: string
  question: string
  session_id?: string | null
  knowledge_id?: string | null
  wiki_page_id?: string | null
  top_k?: number
  use_rag?: boolean
  use_wiki?: boolean
  use_profile?: boolean
  stream?: boolean
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
  model?: string | null
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
