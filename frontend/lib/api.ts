export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
const API_BASE_OVERRIDE_KEY = "zhixue_api_base"

function getRuntimeApiBaseUrl(): string {
  if (typeof window === "undefined") {
    return API_BASE_URL
  }

  const queryBase = new URLSearchParams(window.location.search).get("api_base")
  if (queryBase) {
    window.localStorage.setItem(API_BASE_OVERRIDE_KEY, queryBase)
    return queryBase
  }

  return window.localStorage.getItem(API_BASE_OVERRIDE_KEY) || API_BASE_URL
}

export function buildApiUrl(path: string): string {
  if (/^https?:\/\//.test(path)) {
    return path
  }
  const baseUrl = getRuntimeApiBaseUrl().replace(/\/$/, "")
  const normalizedPath = path.startsWith("/") ? path : `/${path}`
  if (baseUrl.endsWith("/api/v1") && normalizedPath.startsWith("/api/v1/")) {
    return `${baseUrl}${normalizedPath.slice("/api/v1".length)}`
  }
  return `${baseUrl}${normalizedPath}`
}
