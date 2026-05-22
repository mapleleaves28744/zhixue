export interface ApiResponse<T> {
  code: number
  message: string
  data: T
  request_id: string
}

export interface ApiErrorResponse {
  code: number
  message: string
  detail?: unknown
  request_id?: string
}

export interface PageData<T> {
  items: T[]
  page: number
  page_size: number
  total: number
}
