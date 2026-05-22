import type { ApiErrorResponse, ApiResponse } from "@/types/api"
import { buildApiUrl } from "@/lib/api"
import { clearAuthSession, getToken } from "@/lib/auth"

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown
  redirectOnUnauthorized?: boolean
}

export class RequestError extends Error {
  code: number
  detail?: unknown
  requestId?: string
  status: number

  constructor(message: string, status: number, code: number, detail?: unknown, requestId?: string) {
    super(message)
    this.name = "RequestError"
    this.status = status
    this.code = code
    this.detail = detail
    this.requestId = requestId
  }
}

function stringifyDetail(detail: unknown): string | null {
  if (typeof detail === "string") {
    return detail
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") {
          return item
        }
        if (item && typeof item === "object" && "msg" in item) {
          return String(item.msg)
        }
        return null
      })
      .filter(Boolean)
      .join("；")
  }
  return null
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = getToken()
  const headers = new Headers(options.headers)
  headers.set("Accept", "application/json")

  const body = options.body
  if (body !== undefined && !(body instanceof FormData)) {
    headers.set("Content-Type", "application/json")
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`)
  }

  const response = await fetch(buildApiUrl(path), {
    ...options,
    headers,
    body: body === undefined || body instanceof FormData ? body : JSON.stringify(body)
  })

  let payload: ApiResponse<T> | ApiErrorResponse | null = null
  try {
    payload = (await response.json()) as ApiResponse<T> | ApiErrorResponse
  } catch {
    payload = null
  }

  if (!response.ok || !payload || payload.code !== 0) {
    const errorPayload = payload as ApiErrorResponse | null
    const detailText = stringifyDetail(errorPayload?.detail)
    const message =
      detailText ||
      errorPayload?.message ||
      (response.status === 401 ? "登录状态已失效，请重新登录" : "请求失败，请稍后重试")

    if (response.status === 401 && options.redirectOnUnauthorized !== false && typeof window !== "undefined") {
      clearAuthSession()
      const current = `${window.location.pathname}${window.location.search}`
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = `/login?redirect=${encodeURIComponent(current)}`
      }
    }

    throw new RequestError(
      message,
      response.status,
      errorPayload?.code ?? response.status,
      errorPayload?.detail,
      errorPayload?.request_id
    )
  }

  return (payload as ApiResponse<T>).data
}
