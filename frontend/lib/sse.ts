import { buildApiUrl } from "@/lib/api"
import { getToken } from "@/lib/auth"

export type SseHandlers = {
  onOpen?: () => void
  onClose?: () => void
  onEvent?: (eventName: string, data: Record<string, unknown>) => void
  signal?: AbortSignal
}

export async function consumeSseStream(
  url: string,
  handlers: SseHandlers,
  init?: RequestInit,
): Promise<void> {
  const token = getToken()
  const response = await fetch(buildApiUrl(url), {
    ...init,
    signal: handlers.signal ?? init?.signal,
    headers: {
      Accept: "text/event-stream",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const detail =
      typeof payload?.detail === "string"
        ? payload.detail
        : payload?.message || `SSE 连接失败 (${response.status})`
    throw new Error(detail)
  }

  if (!response.body) {
    throw new Error("浏览器不支持流式响应")
  }

  handlers.onOpen?.()
  const reader = response.body.getReader()
  const decoder = new TextDecoder("utf-8")
  let buffer = ""

  function consumeEvent(rawEvent: string) {
    const lines = rawEvent.split("\n").map((line) => line.trimEnd())
    const eventName = (lines.find((line) => line.startsWith("event:")) || "event: message").slice(6).trim()
    const dataLines = lines.filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trimStart())
    if (!dataLines.length) return
    const eventData = JSON.parse(dataLines.join("\n")) as Record<string, unknown>
    handlers.onEvent?.(eventName, eventData)
  }

  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
    const events = buffer.split("\n\n")
    buffer = events.pop() || ""
    for (const eventText of events) {
      if (eventText.trim()) consumeEvent(eventText)
    }
    if (done) break
  }
  if (buffer.trim()) consumeEvent(buffer)
  handlers.onClose?.()
}
