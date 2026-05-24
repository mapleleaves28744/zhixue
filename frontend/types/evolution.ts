export interface EvolutionStrategy {
  id: string
  user_id: string
  course_id: string | null
  strategy_type: string
  before_value: Record<string, unknown>
  after_value: Record<string, unknown>
  description: string | null
  status: string
  risk_level: string
  evidence: string[]
  previous_strategy_id: string | null
  version_no: number
  created_at: string
  updated_at: string
}

export interface EvolutionEvent {
  id: string
  user_id: string
  course_id: string | null
  trigger_type: string
  focus: string
  input_snapshot: Record<string, unknown>
  strategies_generated: number
  status: string
  error_message: string | null
  created_at: string
}

export interface AnalyzeResponse {
  event_id: string
  strategies_count: number
  strategies: EvolutionStrategy[]
}
