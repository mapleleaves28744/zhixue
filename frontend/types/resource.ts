export type ResourceType = "explanation" | "summary" | "example" | "flashcard" | "review"

export interface ResourceCitation {
  source_type: string
  source_id?: string
  page_id?: string
  chunk_id?: string
  title?: string
  page_no?: number | null
  score?: number
  quote?: string
}

export interface GeneratedResource {
  id: string
  user_id: string
  course_id: string
  knowledge_id?: string | null
  wiki_page_id?: string | null
  resource_type: ResourceType
  title: string
  content: string
  citations: ResourceCitation[]
  personalized_reason?: string | null
  model_name?: string | null
  prompt_version_id?: string | null
  status: string
  created_at: string
}

export interface ResourceGeneratePayload {
  course_id: string
  knowledge_id?: string | null
  wiki_page_id?: string | null
  resource_type: ResourceType
  requirement?: string | null
  use_profile?: boolean
  save_to_wiki?: boolean
}

export interface ResourceGenerateResult {
  resource_id: string
  title: string
  content: string
  citations: ResourceCitation[]
  personalized_reason?: string | null
  agent_run_id?: string | null
  review_result: Record<string, unknown>
  status: string
  wiki_page_id?: string | null
}
