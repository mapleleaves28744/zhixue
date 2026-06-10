"use client"

import { useCallback, useState } from "react"
import { streamTutorChat } from "@/services/tutorService"
import type { TutorChatRequest, TutorChatResponse } from "@/types/tutor"

export function useTutorStream() {
  const [streaming, setStreaming] = useState(false)
  const [progress, setProgress] = useState<string>("")
  const [answer, setAnswer] = useState("")
  const [result, setResult] = useState<TutorChatResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const send = useCallback(async (payload: TutorChatRequest) => {
    setStreaming(true)
    setProgress("正在准备回答…")
    setAnswer("")
    setResult(null)
    setError(null)

    try {
      const data = await streamTutorChat(payload, {
        onProgress: (p) => setProgress(p.message || p.stage || "处理中…"),
        onDelta: (chunk) => setAnswer((prev) => prev + chunk),
        onDone: (final) => {
          setResult(final)
          setAnswer(final.answer || "")
        },
      })
      if (data) setResult(data)
      return data
    } catch (err) {
      setError(err instanceof Error ? err.message : "请求失败")
      return null
    } finally {
      setStreaming(false)
    }
  }, [])

  const reset = useCallback(() => {
    setStreaming(false)
    setProgress("")
    setAnswer("")
    setResult(null)
    setError(null)
  }, [])

  return { streaming, progress, answer, result, error, send, reset }
}
