export interface WikiPage {
  id: string
  course_id: string
  owner_id: string
  title: string
  slug: string
  summary: string | null
  content: string
  status: string
  current_version: number
  extra_meta: Record<string, unknown>
  created_at: string
  updated_at: string
  sources?: WikiSource[]
}

export interface WikiPageListItem {
  id: string
  course_id: string
  title: string
  slug: string
  summary: string | null
  status: string
  current_version: number
  created_at: string
  updated_at: string
}

export interface WikiPageVersion {
  id: string
  page_id: string
  version_number: number
  title: string
  content: string
  summary: string | null
  change_message: string | null
  created_by: string
  created_at: string
}

export interface WikiSource {
  id: string
  page_id: string
  source_type: string
  source_id: string
  source_title: string | null
  quote_text: string | null
  extra_meta?: Record<string, unknown>
  created_at?: string
}

export interface WikiLink {
  id: string
  source_page_id: string
  target_page_id: string
  relation_type: string
  created_at: string
}

export interface GenerateFromMaterialPayload {
  courseId: string
  materialId: string
}

export interface GenerateFromMaterialResponse {
  generated_count: number
  pages: { id: string; title: string; slug: string; current_version: number }[]
}
