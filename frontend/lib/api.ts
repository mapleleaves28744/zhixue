export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"

export function buildApiUrl(path: string): string {
  if (/^https?:\/\//.test(path)) {
    return path
  }
  const baseUrl = API_BASE_URL.replace(/\/$/, "")
  const normalizedPath = path.startsWith("/") ? path : `/${path}`
  if (baseUrl.endsWith("/api/v1") && normalizedPath.startsWith("/api/v1/")) {
    return `${baseUrl}${normalizedPath.slice("/api/v1".length)}`
  }
  return `${baseUrl}${normalizedPath}`
}
