import { request } from "@/lib/request"

export interface MediaJob {
  id: string
  user_id: string
  course_id: string
  resource_id?: string | null
  asset_id?: string | null
  job_type: string
  provider: string
  stage: string
  status: string
  progress: number
  output_payload: Record<string, unknown>
  error_message?: string | null
  created_at: string
  updated_at: string
  finished_at?: string | null
}

export function getMediaJob(jobId: string): Promise<MediaJob> {
  return request(`/api/v1/multimodal/jobs/${jobId}`)
}
