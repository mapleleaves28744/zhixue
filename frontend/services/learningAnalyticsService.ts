import { request } from "@/lib/request"

type HeartbeatResponse = { session_id: string; active_seconds: number }

export function heartbeatLearningSession(payload: {
  session_id?: string | null
  course_id?: string | null
  page: string
  active: boolean
}): Promise<HeartbeatResponse> {
  return request<HeartbeatResponse>("/learning-analytics/sessions/heartbeat", {
    method: "POST",
    body: payload,
    redirectOnUnauthorized: false,
  })
}

export function endLearningSession(sessionId: string): Promise<HeartbeatResponse> {
  return request<HeartbeatResponse>(`/learning-analytics/sessions/${sessionId}/end`, {
    method: "POST",
    redirectOnUnauthorized: false,
  })
}
