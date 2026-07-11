"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { streamTutorChat } from "@/services/tutorService"
import type { TutorChatRequest, TutorChatResponse } from "@/types/tutor"

export type TutorStreamStatus =
  | "retrieving"
  | "generating"
  | "validating"
  | "completed"
  | "interrupted"
  | "failed"

export interface TutorStreamSnapshot {
  requestId: string
  status: TutorStreamStatus
  progress: string
  answer: string
  result: TutorChatResponse | null
  error: string | null
}

const initialSnapshot = (requestId: string): TutorStreamSnapshot => ({
  requestId,
  status: "retrieving",
  progress: "正在检索课程依据…",
  answer: "",
  result: null,
  error: null,
})

export function useTutorStream({
  onSnapshot,
}: {
  onSnapshot: (snapshot: TutorStreamSnapshot) => void
}) {
  const controllersRef = useRef(new Map<string, AbortController>())
  const snapshotsRef = useRef<Record<string, TutorStreamSnapshot>>({})
  const onSnapshotRef = useRef(onSnapshot)
  const [streams, setStreams] = useState<Record<string, TutorStreamSnapshot>>({})

  useEffect(() => {
    onSnapshotRef.current = onSnapshot
  }, [onSnapshot])

  const update = useCallback(
    (requestId: string, updater: (current: TutorStreamSnapshot) => TutorStreamSnapshot) => {
      const next = updater(snapshotsRef.current[requestId] || initialSnapshot(requestId))
      snapshotsRef.current = { ...snapshotsRef.current, [requestId]: next }
      setStreams(snapshotsRef.current)
      onSnapshotRef.current(next)
    },
    [],
  )

  const start = useCallback(
    async (requestId: string, payload: TutorChatRequest): Promise<TutorChatResponse | null> => {
      controllersRef.current.get(requestId)?.abort()
      const controller = new AbortController()
      controllersRef.current.set(requestId, controller)
      const first = initialSnapshot(requestId)
      snapshotsRef.current = { ...snapshotsRef.current, [requestId]: first }
      setStreams(snapshotsRef.current)
      onSnapshotRef.current(first)
      const updateCurrent = (
        updater: (current: TutorStreamSnapshot) => TutorStreamSnapshot,
      ) => {
        if (controllersRef.current.get(requestId) !== controller) return
        update(requestId, updater)
      }

      try {
        return await streamTutorChat(payload, {
          signal: controller.signal,
          onProgress: ({ stage, message }) => {
            const status: TutorStreamStatus =
              stage === "validate_citations"
                ? "validating"
                : stage === "llm_generation"
                  ? "generating"
                  : "retrieving"
            updateCurrent((current) => ({
              ...current,
              status,
              progress: message || stage || "处理中…",
            }))
          },
          onEvidence: (evidence) => {
            updateCurrent((current) => ({
              ...current,
              progress: evidence.grounding_message || current.progress,
            }))
          },
          onDelta: (content) => {
            updateCurrent((current) => ({
              ...current,
              status: "generating",
              answer: `${current.answer}${content}`,
            }))
          },
          onDone: (result) => {
            updateCurrent((current) => ({
              ...current,
              status: "completed",
              progress: "",
              answer: result.answer || current.answer,
              result,
              error: null,
            }))
          },
          onInterrupted: (error) => {
            updateCurrent((current) => ({
              ...current,
              status: "interrupted",
              progress: "生成已中断",
              error: error.message,
            }))
          },
        })
      } catch (error) {
        if (controller.signal.aborted) return null
        const message = error instanceof Error ? error.message : "请求失败"
        updateCurrent((current) => ({
          ...current,
          status: "failed",
          progress: "",
          error: message,
        }))
        return null
      } finally {
        if (controllersRef.current.get(requestId) === controller) {
          controllersRef.current.delete(requestId)
        }
      }
    },
    [update],
  )

  const stop = useCallback(
    (requestId: string) => {
      const controller = controllersRef.current.get(requestId)
      if (!controller) return
      controller.abort()
      controllersRef.current.delete(requestId)
      update(requestId, (current) => ({
        ...current,
        status: "interrupted",
        progress: "已停止生成",
      }))
    },
    [update],
  )

  const stopAll = useCallback(() => {
    const requestIds = [...controllersRef.current.keys()]
    for (const controller of controllersRef.current.values()) controller.abort()
    controllersRef.current.clear()
    for (const requestId of requestIds) {
      update(requestId, (current) => ({
        ...current,
        status: "interrupted",
        progress: "已停止生成",
      }))
    }
  }, [update])

  useEffect(
    () => () => {
      for (const controller of controllersRef.current.values()) controller.abort()
      controllersRef.current.clear()
    },
    [],
  )

  return { streams, start, stop, stopAll }
}
