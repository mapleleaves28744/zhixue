export interface StudentMemory {
  id: string
  user_id: string
  course_id: string | null
  memory_type: string
  content: string
  evidence: string[]
  confidence: number
  created_at: string
  updated_at: string
}

export interface MemoryUpdate {
  content?: string
  memory_type?: string
}
