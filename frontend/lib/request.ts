export interface ApiResponse<T> {
  code: number
  message: string
  data: T
  request_id: string
}

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1"
