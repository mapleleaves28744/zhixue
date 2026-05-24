import { request } from "@/lib/request"
import type { PageData } from "@/types/api"
import type { AnalyzeResponse, EvolutionEvent, EvolutionStrategy } from "@/types/evolution"

export function analyze(courseId: string, focus: string): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>("/api/v1/evolution/analyze", {
    method: "POST",
    body: { course_id: courseId, focus },
  })
}

export function listStrategies(params?: {
  courseId?: string
  strategyType?: string
  status?: string
  page?: number
  pageSize?: number
}): Promise<PageData<EvolutionStrategy>> {
  const searchParams = new URLSearchParams()
  if (params?.courseId) searchParams.set("course_id", params.courseId)
  if (params?.strategyType) searchParams.set("strategy_type", params.strategyType)
  if (params?.status) searchParams.set("status", params.status)
  searchParams.set("page", String(params?.page ?? 1))
  searchParams.set("page_size", String(params?.pageSize ?? 20))
  return request<PageData<EvolutionStrategy>>(`/api/v1/evolution/strategies?${searchParams.toString()}`)
}

export function getStrategy(strategyId: string): Promise<EvolutionStrategy> {
  return request<EvolutionStrategy>(`/api/v1/evolution/strategies/${strategyId}`)
}

export function applyStrategy(strategyId: string): Promise<EvolutionStrategy> {
  return request<EvolutionStrategy>("/api/v1/evolution/strategies/apply", {
    method: "POST",
    body: { strategy_id: strategyId },
  })
}

export function rollbackStrategy(strategyId: string): Promise<EvolutionStrategy> {
  return request<EvolutionStrategy>(`/api/v1/evolution/strategies/${strategyId}/rollback`, {
    method: "POST",
  })
}

export function listEvents(params?: {
  courseId?: string
  page?: number
  pageSize?: number
}): Promise<PageData<EvolutionEvent>> {
  const searchParams = new URLSearchParams()
  if (params?.courseId) searchParams.set("course_id", params.courseId)
  searchParams.set("page", String(params?.page ?? 1))
  searchParams.set("page_size", String(params?.pageSize ?? 20))
  return request<PageData<EvolutionEvent>>(`/api/v1/evolution/events?${searchParams.toString()}`)
}
