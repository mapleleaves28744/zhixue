"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { ReactorCard } from "./ReactorCard"
import type { ReactorCard as ReactorCardType, ReactorConfig, ReactorEventType } from "./types"

interface ReactorContainerProps extends ReactorConfig {
  /** 额外的请求体（POST 方式发起） */
  body?: Record<string, unknown>
  /** 是否自动开始 */
  autoStart?: boolean
  /** 完成回调 */
  onComplete?: (cards: ReactorCardType[]) => void
  /** 错误回调 */
  onError?: (error: string) => void
  className?: string
}

export function ReactorContainer({
  url,
  headers = {},
  body,
  maxCards = 20,
  autoStart = true,
  onComplete,
  onError,
  className,
}: ReactorContainerProps) {
  const [cards, setCards] = useState<ReactorCardType[]>([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const startStream = useCallback(async () => {
    // 清理上一次连接
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setCards([])
    setConnected(true)
    setError(null)

    try {
      const fetchHeaders: Record<string, string> = {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        ...headers,
      }

      const response = await fetch(url, {
        method: body ? "POST" : "GET",
        headers: fetchHeaders,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error("ReadableStream not supported")

      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() || ""

        let currentEvent = ""
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith("data: ")) {
            const dataStr = line.slice(6)
            if (dataStr.trim() === "[DONE]") {
              handleEvent("done", {})
              continue
            }
            try {
              const data = JSON.parse(dataStr)
              handleEvent(currentEvent || "delta", data)
            } catch {
              // 非 JSON 数据，作为纯文本
              handleEvent(currentEvent || "delta", { content: dataStr })
            }
          }
        }
      }

      handleEvent("done", {})
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") return
      const msg = err instanceof Error ? err.message : "连接失败"
      setError(msg)
      onError?.(msg)
    } finally {
      setConnected(false)
    }
  }, [url, headers, body, onError])

  const handleEvent = useCallback(
    (eventType: string, data: Record<string, unknown>) => {
      const event = eventType as ReactorEventType

      setCards((prev) => {
        const next = [...prev]

        switch (event) {
          case "card_start": {
            const card: ReactorCardType = {
              id: String(data.card_id || `card-${Date.now()}`),
              type: String(data.card_type || "text"),
              title: String(data.title || ""),
              content: String(data.content || ""),
              status: "streaming",
              metadata: data,
            }
            if (next.length < maxCards) next.push(card)
            break
          }

          case "card_update":
          case "delta": {
            const targetId = String(data.card_id || "")
            const target = targetId
              ? next.find((c) => c.id === targetId)
              : next[next.length - 1]
            if (target) {
              target.content += String(data.content || "")
              target.status = "streaming"
            } else if (next.length < maxCards) {
              // 没有目标卡片，创建一个
              next.push({
                id: `card-${Date.now()}`,
                type: "text",
                title: "",
                content: String(data.content || ""),
                status: "streaming",
              })
            }
            break
          }

          case "card_end": {
            const targetId = String(data.card_id || "")
            const target = targetId
              ? next.find((c) => c.id === targetId)
              : next[next.length - 1]
            if (target) {
              target.status = "complete"
              if (data.content) target.content = String(data.content)
            }
            break
          }

          case "done":
            next.forEach((c) => {
              if (c.status === "streaming") c.status = "complete"
            })
            onComplete?.(next)
            break

          case "error":
            next.forEach((c) => {
              if (c.status === "streaming") c.status = "error"
            })
            setError(String(data.message || "生成失败"))
            break
        }

        return next
      })
    },
    [maxCards, onComplete],
  )

  // 自动开始
  useEffect(() => {
    if (autoStart) {
      startStream()
    }
    return () => {
      abortRef.current?.abort()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className={className} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* 状态栏 */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: 13,
          color: "#857462",
        }}
      >
        <span>
          {connected ? "🔄 正在生成…" : error ? `❌ ${error}` : `✅ 完成（${cards.length} 张卡片）`}
        </span>
        {!connected && (
          <button
            onClick={startStream}
            style={{
              padding: "4px 12px",
              borderRadius: 8,
              border: "1px solid #d7c3ae",
              background: "transparent",
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            重新生成
          </button>
        )}
      </div>

      {/* 卡片列表 */}
      {cards.map((card) => (
        <ReactorCard key={card.id} card={card} />
      ))}

      {/* 光标闪烁动画 CSS */}
      <style>{`@keyframes blink { 50% { opacity: 0; } }`}</style>
    </div>
  )
}
