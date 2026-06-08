"use client"

import { useCallback, useRef, useState } from "react"
import {
  getAgentTask,
  requeueAgentTask,
  resumeAgentTask,
  streamAgentTaskEvents,
} from "@/services/agentService"
import type { AgentTask, AgentTaskEvent } from "@/types/agent"

export function useAgentTaskStream() {
  const [events, setEvents] = useState<AgentTaskEvent[]>([])
  const [task, setTask] = useState<AgentTask | null>(null)
  const [streaming, setStreaming] = useState(false)
  const [finalAnswer, setFinalAnswer] = useState<string>("")
  const [error, setError] = useState<string | null>(null)
  const watchingRef = useRef<string | null>(null)

  const watchTask = useCallback(async (taskId: string) => {
    if (watchingRef.current === taskId) return
    watchingRef.current = taskId
    setStreaming(true)
    setEvents([])
    setFinalAnswer("")
    setError(null)

    let queuedGuard: ReturnType<typeof setTimeout> | null = null
    queuedGuard = setTimeout(async () => {
      try {
        const current = await getAgentTask(taskId)
        if (current.status === "queued") {
          await requeueAgentTask(taskId)
        }
      } catch {
        /* ignore requeue errors */
      }
    }, 12000)

    try {
      await streamAgentTaskEvents(taskId, {
        onEvent: async (eventType, data) => {
          if (eventType !== "heartbeat") {
            setEvents((prev) => [...prev, { type: eventType, data }])
          }
          if (eventType === "completed") {
            setFinalAnswer(String(data.final_answer || ""))
          }
          if (eventType === "failed") {
            setError(String(data.error_message || "任务失败"))
          }
          try {
            const updated = await getAgentTask(taskId)
            setTask(updated)
          } catch {
            /* ignore refresh errors */
          }
        },
      })
      const finalTask = await getAgentTask(taskId)
      setTask(finalTask)
    } catch (err) {
      setError(err instanceof Error ? err.message : "事件流连接失败")
    } finally {
      if (queuedGuard) clearTimeout(queuedGuard)
      setStreaming(false)
      watchingRef.current = null
    }
  }, [])

  const approve = useCallback(async (taskId: string, approved: boolean) => {
    const updated = await resumeAgentTask(taskId, approved)
    setTask(updated)
    if (approved) await watchTask(taskId)
  }, [watchTask])

  const reset = useCallback(() => {
    setEvents([])
    setTask(null)
    setStreaming(false)
    setFinalAnswer("")
    setError(null)
    watchingRef.current = null
  }, [])

  return { events, task, streaming, finalAnswer, error, watchTask, approve, reset }
}
