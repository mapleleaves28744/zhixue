export interface LearningPathItem {
  id: string
  path_id: string
  knowledge_id?: string | null
  wiki_page_id?: string | null
  title: string
  item_type: string
  order_index: number
  status: "pending" | "doing" | "completed" | "skipped"
  reason?: string | null
  estimated_minutes?: number | null
  completed_at?: string | null
  created_at: string
}

export interface LearningPath {
  id: string
  user_id: string
  course_id: string
  title: string
  goal?: string | null
  reason?: string | null
  status: string
  progress: number
  strategy_version_id?: string | null
  created_at: string
  updated_at: string
  items: LearningPathItem[]
}

export interface LearningPathGeneratePayload {
  course_id: string
  goal?: string
  target_knowledge_ids?: string[]
  path_type?: string
}
