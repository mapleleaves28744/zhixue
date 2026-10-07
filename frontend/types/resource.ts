export type ResourceType =
  | "explanation"
  | "summary"
  | "example"
  | "flashcard"
  | "review"
  | "mindmap"
  | "diagram"
  | "image"
  | "video"
  | "animation"
  | "interactive_courseware"
  | "immersive_classroom"
  | "code_project"
  | "reading_pack"

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
  previous_resource_id?: string | null
  revision_no?: number
  status: string
  created_at: string
  media_asset_id?: string | null
  media_mime_type?: string | null
  media_asset_type?: string | null
  media_file_url?: string | null
  content_format?: string | null
  preview_mode?: "image" | "audio" | "video" | "mermaid" | "html" | "immersive_classroom" | "text" | null
  media_job_id?: string | null
  job_status?: string | null
  preview_video_asset_id?: string | null
  preview_video_mime_type?: string | null
}

export type GeneratedResourceListItem = Pick<
  GeneratedResource,
  | "id"
  | "user_id"
  | "course_id"
  | "knowledge_id"
  | "wiki_page_id"
  | "resource_type"
  | "title"
  | "personalized_reason"
  | "previous_resource_id"
  | "revision_no"
  | "status"
  | "created_at"
  | "content_format"
  | "preview_mode"
  | "media_job_id"
  | "job_status"
>

export interface ResourceGeneratePayload {
  course_id: string
  topic?: string | null
  knowledge_id?: string | null
  wiki_page_id?: string | null
  resource_type: ResourceType
  requirement?: string | null
  use_profile?: boolean
  save_to_wiki?: boolean
}

export interface ResourceGenerateResult {
  resource_id: string
  id: string
  resource_type: ResourceType
  title: string
  content: string
  citations: ResourceCitation[]
  previous_resource_id?: string | null
  revision_no?: number
  personalized_reason?: string | null
  agent_run_id?: string | null
  review_result: Record<string, unknown>
  status: string
  wiki_page_id?: string | null
  created_at?: string
  media_asset_id?: string | null
  media_mime_type?: string | null
  media_asset_type?: string | null
  media_file_url?: string | null
  content_format?: string | null
  preview_mode?: "image" | "audio" | "video" | "mermaid" | "html" | "immersive_classroom" | "text" | null
  media_job_id?: string | null
  job_status?: string | null
  job_message?: string | null
}
