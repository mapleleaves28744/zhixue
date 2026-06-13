import { request } from "@/lib/request"

export interface EvolutionStrategy {
  id: string
  strategy_type: string
  description: string
  before_value: Record<string, unknown>
  after_value: Record<string, unknown>
  risk_level: "low" | "medium" | "high"
  status: "draft" | "active" | "superseded" | "rolled_back" | "rejected"
  version_no: number
  previous_strategy_id: string | null
  created_at: string
}

export interface EvolutionEvent {
  id: string
  trigger_type: string
  focus: string
  created_at: string
}

export function analyzeEvolution(payload: {
  course_id: string
  focus?: string
}): Promise<{ event: EvolutionEvent; strategies: EvolutionStrategy[] }> {
  return request("/api/v1/evolution/analyze", {
    method: "POST",
    body: payload,
  })
}

export function listStrategies(params: {
  course_id?: string
  strategy_type?: string
  status?: string
  page?: number
  page_size?: number
} = {}): Promise<{ items: EvolutionStrategy[]; total: number }> {
  const query = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.page_size ?? 20),
  })
  if (params.course_id) query.set("course_id", params.course_id)
  if (params.strategy_type) query.set("strategy_type", params.strategy_type)
  if (params.status) query.set("status", params.status)
  return request(`/api/v1/evolution/strategies?${query}`)
}

export function getStrategy(id: string): Promise<EvolutionStrategy> {
  return request(`/api/v1/evolution/strategies/${id}`)
}

export function applyStrategy(id: string): Promise<EvolutionStrategy> {
  return request("/api/v1/evolution/strategies/apply", {
    method: "POST",
    body: { strategy_id: id },
  })
}

export function rollbackStrategy(id: string): Promise<EvolutionStrategy> {
  return request(`/api/v1/evolution/strategies/${id}/rollback`, {
    method: "POST",
  })
}

export function rejectStrategy(id: string): Promise<EvolutionStrategy> {
  return request(`/api/v1/evolution/strategies/${id}/reject`, {
    method: "POST",
  })
}

export function listEvents(params: {
  course_id?: string
  page?: number
  page_size?: number
} = {}): Promise<{ items: EvolutionEvent[]; total: number }> {
  const query = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.page_size ?? 20),
  })
  if (params.course_id) query.set("course_id", params.course_id)
  return request(`/api/v1/evolution/events?${query}`)
}
