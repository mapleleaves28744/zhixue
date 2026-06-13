export interface LearningPathItem {
  id: string
  path_id: string
  title: string
  item_type: string
  order_index: number
  status: string
  reason?: string | null
  estimated_minutes?: number | null
}

export interface LearningPathDetail {
  id: string
  course_id: string
  title: string
  goal?: string | null
  reason?: string | null
  status: string
  progress: number
  items: LearningPathItem[]
}
