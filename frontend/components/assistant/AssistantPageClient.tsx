"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useSearchParams } from "next/navigation"
import { toast } from "sonner"
import { ActivityDetailDialog } from "@/components/assistant/ActivityDetailDialog"
import { AgentReplyBlock, TutorReplyBlock } from "@/components/assistant/ReplyBlocks"
import {
  extractChatArtifacts,
  extractChatMediaArtifacts,
  extractMediaJobProgress,
  hasMediaJob,
  hasPendingMediaJobs,
} from "@/components/assistant/extractChatArtifacts"
import { extractSpeechAudio } from "@/components/assistant/extractSpeechAudio"
import { ConversationHistoryHover } from "@/components/assistant/ConversationHistoryHover"
import { ModeToggle } from "@/components/assistant/ModeToggle"
import { ResourceSidePanel } from "@/components/assistant/ResourceSidePanel"
import { agentStatusLine } from "@/components/assistant/streamLabels"
import { StudentShell } from "@/components/assistant/StudentShell"
import { ToolSelector } from "@/components/assistant/ToolSelector"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import {
  cancelAgentTask,
  createAgentConversation,
  getAgentTask,
  listAgentConversationMessages,
  listAgentConversations,
  listAgentTaskEvents,
  requeueAgentTask,
  resumeAgentTask,
  sendAgentConversationMessage,
  streamAgentTaskEvents,
} from "@/services/agentService"
import { streamTutorChat } from "@/services/tutorService"
import { resolveCourseIdFromList, resolveCourseIdSyncFallback } from "@/lib/resolveCourse"
import { getResourceTypeLabel, normalizeResourceType } from "@/lib/resourceTypes"
import { listCourses } from "@/services/courseService"
import { listWikiPages } from "@/services/wikiService"
import type { AgentMessage, AgentTask, AgentTaskEvent, AssistantMode } from "@/types/agent"
import { AGENT_ONLY_TOOLS } from "@/types/agent"
import type { Course } from "@/types/course"
import type { ResourceType } from "@/types/resource"
import type { WikiPageSummary } from "@/services/wikiService"
import type { TutorCitation } from "@/types/tutor"
import { normalizeAgentAnswer } from "@/lib/normalizeAgentAnswer"
import { endLearningSession, heartbeatLearningSession } from "@/services/learningAnalyticsService"

const COURSE_KEY = "zhixue_current_course_id"
const CONVERSATION_KEY = "zhixue_agent_conversation_id"

type ChatItem =
  | { id: string; kind: "user"; content: string }
  | {
      id: string
      kind: "tutor"
      content: string
      streaming?: boolean
      progress?: string
      error?: string | null
      citations?: TutorCitation[]
    }
  | {
      id: string
      kind: "agent"
      taskId: string
      userQuestion: string
      events: AgentTaskEvent[]
      task: AgentTask | null
      finalAnswer: string
      streaming: boolean
      paused?: boolean
      error: string | null
      payloadArtifacts?: Record<string, unknown>[]
    }

type DetailTarget = { kind: "tutor"; messageId: string } | { kind: "agent"; taskId: string }

const RESOURCE_ARTIFACT_TYPES = new Set(["resource", "media_asset"])
const TERMINAL_TASK_STATUSES = new Set(["succeeded", "failed", "cancelled"])

function isTaskTerminal(status?: string | null): boolean {
  return Boolean(status && TERMINAL_TASK_STATUSES.has(status))
}

function isResourceArtifact(ref: unknown): boolean {
  if (!ref || typeof ref !== "object") return false
  const item = ref as Record<string, unknown>
  const type = String(item.type || "")
  if (RESOURCE_ARTIFACT_TYPES.has(type)) return true
  return Boolean(item.resource_id)
}

function resourceTypeFromArtifact(ref: unknown): ResourceType | null {
  if (!ref || typeof ref !== "object") return null
  const item = ref as Record<string, unknown>
  const candidates = [
    item.resource_type,
    item.subtype,
    item.asset_type,
    item.preview_mode,
    typeof item.type === "string" && item.type === "media_job" ? item.subtype : null,
  ]
  for (const candidate of candidates) {
    const normalized = normalizeResourceType(candidate)
    if (normalized) return normalized
  }
  return null
}

function resourceTypeFromArtifacts(value: unknown): ResourceType | null {
  if (!Array.isArray(value)) return null
  for (const item of value) {
    const normalized = resourceTypeFromArtifact(item)
    if (normalized) return normalized
  }
  return null
}

function resourceTypeFromEvent(eventType: string, data: Record<string, unknown>): ResourceType | null {
  if (eventType === "tool_completed") {
    return resourceTypeFromArtifacts(data.artifact_refs)
  }
  if (eventType === "completed") {
    return resourceTypeFromArtifacts(data.artifacts)
  }
  if (eventType === "multimodal_progress") {
    return resourceTypeFromArtifacts(data.artifact_refs)
  }
  return null
}

function eventProducesResource(eventType: string, data: Record<string, unknown>): boolean {
  if (eventType === "tool_completed" && data.success === false) return false
  if (eventType === "tool_completed") {
    const refs = data.artifact_refs
    return Array.isArray(refs) && refs.some(isResourceArtifact)
  }
  if (eventType === "completed") {
    const artifacts = data.artifacts
    return Array.isArray(artifacts) && artifacts.some(isResourceArtifact)
  }
  return false
}

function upsertAgentEvent(
  events: AgentTaskEvent[],
  eventType: string,
  data: Record<string, unknown>,
): AgentTaskEvent[] {
  if (eventType === "multimodal_progress" && data.job_id) {
    const jobId = String(data.job_id)
    const existingIndex = events.findIndex(
      (event) => event.type === "multimodal_progress" && String(event.data.job_id) === jobId,
    )
    if (existingIndex >= 0) {
      const next = [...events]
      next[existingIndex] = { type: eventType, data }
      return next
    }
  }
  return [...events, { type: eventType, data }]
}

async function hydrateAgentMessage(
  item: Extract<ChatItem, { kind: "agent" }>,
): Promise<Extract<ChatItem, { kind: "agent" }>> {
  try {
    const [task, history] = await Promise.all([getAgentTask(item.taskId), listAgentTaskEvents(item.taskId)])
    const events: AgentTaskEvent[] = history.items.map((evt) => ({
      type: evt.event_type,
      data: evt.payload,
    }))
    const completed = [...events].reverse().find((e) => e.type === "completed")
    const failed = [...events].reverse().find((e) => e.type === "failed")
    const terminal = isTaskTerminal(task.status)
    return {
      ...item,
      task,
      events,
      finalAnswer: completed
        ? normalizeAgentAnswer(String(completed.data.final_answer || item.finalAnswer))
        : item.finalAnswer,
      error: failed ? String(failed.data.error_message || "任务失败") : task.error_message || item.error,
      streaming: !terminal,
      paused: false,
    }
  } catch {
    return item
  }
}

function messagesFromHistory(items: AgentMessage[]): ChatItem[] {
  const result: ChatItem[] = []
  let lastUserContent = ""

  for (const m of items.slice(-40)) {
    if (m.role === "user") {
      lastUserContent = m.content
      result.push({ id: m.id, kind: "user", content: m.content })
      continue
    }
    if (m.task_id) {
      result.push({
        id: m.id,
        kind: "agent",
        taskId: m.task_id,
        userQuestion: lastUserContent,
        events: [],
        task: null,
        finalAnswer: normalizeAgentAnswer(m.content),
        streaming: false,
        error: null,
        payloadArtifacts: (m.payload?.artifacts as Record<string, unknown>[]) || [],
      })
      continue
    }
    result.push({
      id: m.id,
      kind: "tutor",
      content: m.content,
      citations: (m.payload?.citations as TutorCitation[]) || [],
    })
  }
  return result
}

export function AssistantPageClient() {
  const searchParams = useSearchParams()
  const [courses, setCourses] = useState<Course[]>([])
  const [courseId, setCourseId] = useState("")
  const learningSessionIdRef = useRef<string | null>(null)
  const lastLearningActivityAtRef = useRef(Date.now())
  const [wikiPages, setWikiPages] = useState<WikiPageSummary[]>([])
  const [wikiPageId, setWikiPageId] = useState<string>("")
  const [mode, setMode] = useState<AssistantMode>("fast")
  const [toolHints, setToolHints] = useState<string[]>([])
  const [useRag, setUseRag] = useState(true)
  const [useWiki, setUseWiki] = useState(true)
  const [input, setInput] = useState("")
  const [messages, setMessages] = useState<ChatItem[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const [activeTutorId, setActiveTutorId] = useState<string | null>(null)
  const [detailTarget, setDetailTarget] = useState<DetailTarget | null>(null)
  const [resourceRefreshSignal, setResourceRefreshSignal] = useState(0)
  const [resourceRevealType, setResourceRevealType] = useState<ResourceType | null>(
    () => normalizeResourceType(searchParams.get("resource_type")),
  )
  const listRef = useRef<HTMLDivElement>(null)
  const scrollOnNextRenderRef = useRef(false)
  const initialHistoryScrollRef = useRef(false)
  const watchingTasksRef = useRef<Set<string>>(new Set())
  const agentStreamControllersRef = useRef<Map<string, AbortController>>(new Map())
  const tutorStreamControllersRef = useRef<Map<string, AbortController>>(new Map())
  const resourceSyncedTasksRef = useRef<Set<string>>(new Set())

  const bumpResourceList = useCallback((targetType: ResourceType | null = null) => {
    if (targetType) setResourceRevealType(targetType)
    setResourceRefreshSignal((n) => n + 1)
  }, [])

  useEffect(() => {
    const routeType = normalizeResourceType(searchParams.get("resource_type"))
    if (routeType) setResourceRevealType(routeType)
  }, [searchParams])

  useEffect(() => {
    if (!courseId) return
    const markActive = () => {
      lastLearningActivityAtRef.current = Date.now()
    }
    const heartbeat = async () => {
      try {
        const result = await heartbeatLearningSession({
          session_id: learningSessionIdRef.current,
          course_id: courseId,
          page: "/assistant",
          active: document.visibilityState === "visible" && Date.now() - lastLearningActivityAtRef.current <= 120_000,
        })
        learningSessionIdRef.current = result.session_id
      } catch {}
    }
    window.addEventListener("click", markActive, { passive: true })
    window.addEventListener("keydown", markActive, { passive: true })
    window.addEventListener("scroll", markActive, { passive: true })
    void heartbeat()
    const timer = window.setInterval(heartbeat, 30_000)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener("click", markActive)
      window.removeEventListener("keydown", markActive)
      window.removeEventListener("scroll", markActive)
      if (learningSessionIdRef.current) void endLearningSession(learningSessionIdRef.current).catch(() => {})
    }
  }, [courseId])

  useEffect(() => {
    const q = searchParams.get("question")
    if (q) setInput(q)
  }, [searchParams])

  useEffect(() => {
    listCourses()
      .then(async (data) => {
        setCourses(data.items)
        const urlCourseId = searchParams.get("course_id")
        if (!data.items.length) {
          setCourseId("")
          return
        }
        try {
          const initial = await resolveCourseIdFromList(data.items, urlCourseId)
          setCourseId(initial)
        } catch {
          setCourseId(resolveCourseIdSyncFallback(data.items))
        }
      })
      .catch(() => toast.error("加载课程失败"))
  }, [searchParams])

  useEffect(() => {
    if (!courseId) return
    localStorage.setItem(COURSE_KEY, courseId)
    listWikiPages(courseId)
      .then((data) => {
        setWikiPages(data.items)
        setWikiPageId(data.items[0]?.id || "")
      })
      .catch(() => setWikiPages([]))
  }, [courseId])

  useEffect(() => {
    if (!scrollOnNextRenderRef.current) return
    scrollOnNextRenderRef.current = false
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: initialHistoryScrollRef.current ? "smooth" : "auto",
    })
    initialHistoryScrollRef.current = true
  }, [messages])

  const requestScrollToBottom = useCallback((smooth = true) => {
    scrollOnNextRenderRef.current = true
    if (!smooth) initialHistoryScrollRef.current = false
  }, [])

  const ensureConversation = useCallback(async () => {
    if (conversationId) return conversationId
    if (!courseId) throw new Error("请先选择课程")
    const saved = localStorage.getItem(`${CONVERSATION_KEY}_${courseId}`)
    if (saved) {
      setConversationId(saved)
      return saved
    }
    const conv = await createAgentConversation({ course_id: courseId })
    localStorage.setItem(`${CONVERSATION_KEY}_${courseId}`, conv.id)
    setConversationId(conv.id)
    return conv.id
  }, [conversationId, courseId])

  const watchAgentTaskRef = useRef<(taskId: string) => void>(() => {})
  const stopVisibleStreamsRef = useRef<() => void>(() => {})

  const hydrateHistoryMessages = useCallback(async (items: AgentMessage[]) => {
    const base = messagesFromHistory(items)
    const hydrated = await Promise.all(
      base.map(async (item) => (item.kind === "agent" ? hydrateAgentMessage(item) : item)),
    )
    setMessages(hydrated)
    if (!initialHistoryScrollRef.current) {
      requestScrollToBottom(false)
    }
    for (const item of hydrated) {
      if (
        item.kind === "agent" &&
        (item.streaming || hasPendingMediaJobs(item.events)) &&
        !watchingTasksRef.current.has(item.taskId)
      ) {
        watchAgentTaskRef.current(item.taskId)
      }
    }
  }, [requestScrollToBottom])

  const applyConversation = useCallback(
    async (id: string, items: AgentMessage[]) => {
      stopVisibleStreamsRef.current()
      setDetailTarget(null)
      setConversationId(id)
      localStorage.setItem(`${CONVERSATION_KEY}_${courseId}`, id)
      await hydrateHistoryMessages(items)
    },
    [courseId, hydrateHistoryMessages],
  )

  const loadHistory = useCallback(async () => {
    if (!conversationId) return
    try {
      const { items } = await listAgentConversationMessages(conversationId)
      await hydrateHistoryMessages(items)
    } catch {
      /* ignore */
    }
  }, [conversationId, hydrateHistoryMessages])

  useEffect(() => {
    if (!courseId) return
    const initConversation = async () => {
      let saved = searchParams.get("conversation_id") || localStorage.getItem(`${CONVERSATION_KEY}_${courseId}`)
      if (!saved) {
        try {
          const { items } = await listAgentConversations()
          const latest = items
            .filter((c) => c.course_id === courseId)
            .sort((a, b) => {
              const ta = new Date(a.last_message_at || a.updated_at).getTime()
              const tb = new Date(b.last_message_at || b.updated_at).getTime()
              return tb - ta
            })[0]
          if (latest) {
            saved = latest.id
            localStorage.setItem(`${CONVERSATION_KEY}_${courseId}`, saved)
          }
        } catch {
          /* ignore */
        }
      }
      setConversationId(saved)
    }
    void initConversation()
  }, [courseId])

  useEffect(() => {
    void loadHistory()
  }, [loadHistory])

  const patchAgentMessage = useCallback((taskId: string, patch: Partial<Extract<ChatItem, { kind: "agent" }>>) => {
    setMessages((prev) => prev.map((m) => (m.kind === "agent" && m.taskId === taskId ? { ...m, ...patch } : m)))
  }, [])

  const stopAgentStream = useCallback(
    (taskId: string, options: { markPaused?: boolean } = {}) => {
      const markPaused = options.markPaused ?? true
      agentStreamControllersRef.current.get(taskId)?.abort()
      agentStreamControllersRef.current.delete(taskId)
      watchingTasksRef.current.delete(taskId)
      if (markPaused) {
        patchAgentMessage(taskId, {
          streaming: false,
          paused: true,
          error: null,
        })
      }
    },
    [patchAgentMessage],
  )

  const stopTutorStream = useCallback((messageId: string) => {
    tutorStreamControllersRef.current.get(messageId)?.abort()
    tutorStreamControllersRef.current.delete(messageId)
    setMessages((prev) =>
      prev.map((m) =>
        m.kind === "tutor" && m.id === messageId
          ? { ...m, streaming: false, progress: "已停止生成" }
          : m,
      ),
    )
  }, [])

  const stopVisibleStreams = useCallback(
    (markAgentPaused = true) => {
      for (const messageId of tutorStreamControllersRef.current.keys()) stopTutorStream(messageId)
      for (const taskId of agentStreamControllersRef.current.keys()) {
        stopAgentStream(taskId, { markPaused: markAgentPaused })
      }
      setActiveTutorId(null)
    },
    [stopAgentStream, stopTutorStream],
  )

  useEffect(() => {
    stopVisibleStreamsRef.current = () => stopVisibleStreams(true)
  }, [stopVisibleStreams])

  const watchAgentTask = useCallback(
    async (taskId: string) => {
      if (watchingTasksRef.current.has(taskId)) return
      watchingTasksRef.current.add(taskId)
      const controller = new AbortController()
      agentStreamControllersRef.current.set(taskId, controller)

      let queuedGuard: ReturnType<typeof setTimeout> | null = setTimeout(async () => {
        try {
          const current = await getAgentTask(taskId)
          if (current.status === "queued") await requeueAgentTask(taskId)
        } catch {
          /* ignore */
        }
      }, 4000)

      const syncFromServer = async (): Promise<AgentTaskEvent[] | null> => {
        try {
          const [task, history] = await Promise.all([getAgentTask(taskId), listAgentTaskEvents(taskId)])
          const events = history.items.map((item) => ({
            type: item.event_type,
            data: item.payload,
          }))
          const completed = [...events].reverse().find((e) => e.type === "completed")
          const failed = [...events].reverse().find((e) => e.type === "failed")
          const terminal = isTaskTerminal(task.status)
          setMessages((prev) =>
            prev.map((m) => {
              if (m.kind !== "agent" || m.taskId !== taskId) return m
              return {
                ...m,
                task,
                events,
                finalAnswer: completed
                  ? normalizeAgentAnswer(String(completed.data.final_answer || m.finalAnswer))
                  : m.finalAnswer,
                error: failed ? String(failed.data.error_message || "任务失败") : task.error_message || m.error,
                streaming: !terminal,
                paused: false,
              }
            }),
          )
          if (
            task.status === "succeeded" &&
            !resourceSyncedTasksRef.current.has(taskId) &&
            events.some((e) => eventProducesResource(e.type, e.data as Record<string, unknown>))
          ) {
            resourceSyncedTasksRef.current.add(taskId)
            const targetType =
              events.map((e) => resourceTypeFromEvent(e.type, e.data as Record<string, unknown>)).find(Boolean) ??
              null
            bumpResourceList(targetType)
          }
          return events
        } catch {
          /* ignore poll errors */
          return null
        }
      }

      const pollTimer = setInterval(() => {
        void syncFromServer()
      }, 2500)

      patchAgentMessage(taskId, { streaming: true, paused: false, error: null })

      try {
        await streamAgentTaskEvents(taskId, {
          signal: controller.signal,
          onEvent: async (eventType, data) => {
            if (eventType === "heartbeat") return

            setMessages((prev) =>
              prev.map((m) => {
                if (m.kind !== "agent" || m.taskId !== taskId) return m
                const events = upsertAgentEvent(m.events, eventType, data as Record<string, unknown>)
                const mediaPending = hasPendingMediaJobs(events)
                return {
                  ...m,
                  events,
                  finalAnswer:
                    eventType === "completed"
                      ? normalizeAgentAnswer(String(data.final_answer || m.finalAnswer))
                      : m.finalAnswer,
                  error: eventType === "failed" ? String(data.error_message || "任务失败") : m.error,
                  streaming:
                    !["completed", "failed", "cancelled"].includes(eventType) || mediaPending,
                  paused: false,
                }
              }),
            )

            const targetType = resourceTypeFromEvent(eventType, data as Record<string, unknown>)
            if (
              eventProducesResource(eventType, data as Record<string, unknown>) ||
              (eventType === "multimodal_progress" &&
                Array.isArray((data as Record<string, unknown>).artifact_refs))
            ) {
              bumpResourceList(targetType)
              if (targetType && eventType === "multimodal_progress" && Number(data.progress || 0) >= 100) {
                toast.success(`资源已生成，已放入「${getResourceTypeLabel(targetType)}」分类`)
              }
            }

            if (["tool_started", "tool_completed", "plan_created", "completed"].includes(eventType)) {
              try {
                const updated = await getAgentTask(taskId)
                patchAgentMessage(taskId, { task: updated })
              } catch {
                /* ignore */
              }
            }
          },
        })
        clearInterval(pollTimer)
        const initialBackgroundEvents = await syncFromServer()
        if (
          initialBackgroundEvents &&
          (hasMediaJob(initialBackgroundEvents) || hasPendingMediaJobs(initialBackgroundEvents))
        ) {
          let events = initialBackgroundEvents
          let previousEventCount = events.length
          let stableTerminalPolls = 0
          for (let poll = 0; poll < 720; poll += 1) {
            await new Promise((resolve) => setTimeout(resolve, 2500))
            const refreshed = await syncFromServer()
            if (!refreshed) continue
            events = refreshed
            if (hasPendingMediaJobs(events)) {
              stableTerminalPolls = 0
              patchAgentMessage(taskId, { streaming: true })
            } else if (events.length === previousEventCount) {
              stableTerminalPolls += 1
            } else {
              stableTerminalPolls = 0
            }
            previousEventCount = events.length
            if (stableTerminalPolls >= 4) break
          }
          const targetType =
            events.map((e) => resourceTypeFromEvent(e.type, e.data as Record<string, unknown>)).find(Boolean) ??
            null
          bumpResourceList(targetType)
          patchAgentMessage(taskId, { streaming: false })
        }
      } catch (err) {
        if (controller.signal.aborted) {
          return
        }
        patchAgentMessage(taskId, {
          streaming: false,
          error: err instanceof Error ? err.message : "事件流连接失败",
        })
      } finally {
        if (queuedGuard) clearTimeout(queuedGuard)
        clearInterval(pollTimer)
        agentStreamControllersRef.current.delete(taskId)
        watchingTasksRef.current.delete(taskId)
      }
    },
    [bumpResourceList, patchAgentMessage],
  )

  useEffect(() => {
    watchAgentTaskRef.current = (taskId: string) => {
      void watchAgentTask(taskId)
    }
  }, [watchAgentTask])

  const approveAgentTask = async (taskId: string, approved: boolean) => {
    await resumeAgentTask(taskId, approved)
    if (approved) void watchAgentTask(taskId)
  }

  const resumeAgentTaskView = (taskId: string) => {
    patchAgentMessage(taskId, { paused: false, streaming: true, error: null })
    void watchAgentTask(taskId)
  }

  const cancelAgentTaskView = async (taskId: string) => {
    stopAgentStream(taskId, { markPaused: false })
    try {
      const task = await cancelAgentTask(taskId)
      const history = await listAgentTaskEvents(taskId)
      const events = history.items.map((item) => ({
        type: item.event_type,
        data: item.payload,
      }))
      patchAgentMessage(taskId, {
        task,
        events,
        streaming: false,
        paused: false,
        error: null,
      })
      toast.success("已取消当前 Agent 任务")
    } catch (err) {
      patchAgentMessage(taskId, {
        streaming: false,
        paused: true,
        error: err instanceof Error ? err.message : "取消任务失败",
      })
    }
  }

  const sendMessage = async () => {
    const question = input.trim()
    if (!question || sending) return
    if (!courseId) {
      toast.error("请先选择课程")
      return
    }

    setSending(true)
    setInput("")
    requestScrollToBottom(true)
    setMessages((prev) => [...prev.slice(-49), { id: `u-${Date.now()}`, kind: "user", content: question }])

    try {
      const useAgentPath =
        mode === "agent" || toolHints.some((toolId) => AGENT_ONLY_TOOLS.has(toolId))

      if (!useAgentPath) {
        const tutorId = `t-${Date.now()}`
        const controller = new AbortController()
        tutorStreamControllersRef.current.set(tutorId, controller)
        setActiveTutorId(tutorId)
        setMessages((prev) => [
          ...prev,
          {
            id: tutorId,
            kind: "tutor",
            content: "",
            streaming: true,
            progress: "准备中…",
          },
        ])
        setSending(false)
        void streamTutorChat(
          {
            course_id: courseId,
            question,
            wiki_page_id: wikiPageId || null,
            use_rag: useRag,
            use_wiki: useWiki,
            use_profile: false,
            stream: true,
          },
          {
            signal: controller.signal,
            onProgress: (p) => {
              setMessages((prev) =>
                prev.map((m) =>
                  m.kind === "tutor" && m.id === tutorId
                    ? { ...m, progress: p.message || p.stage || "处理中…" }
                    : m,
                ),
              )
            },
            onDelta: (chunk) => {
              setMessages((prev) =>
                prev.map((m) =>
                  m.kind === "tutor" && m.id === tutorId
                    ? { ...m, content: `${m.content}${chunk}` }
                    : m,
                ),
              )
            },
            onDone: (final) => {
              setMessages((prev) =>
                prev.map((m) =>
                  m.kind === "tutor" && m.id === tutorId
                    ? {
                        ...m,
                        content: final.answer || m.content,
                        streaming: false,
                        progress: undefined,
                        citations: final.citations || m.citations || [],
                      }
                    : m,
                ),
              )
            },
          },
        )
          .catch((err) => {
            if (controller.signal.aborted) return
            setMessages((prev) =>
              prev.map((m) =>
                m.kind === "tutor" && m.id === tutorId
                  ? {
                      ...m,
                      streaming: false,
                      error: err instanceof Error ? err.message : "请求失败",
                    }
                  : m,
              ),
            )
          })
          .finally(() => {
            tutorStreamControllersRef.current.delete(tutorId)
            setActiveTutorId((current) => (current === tutorId ? null : current))
          })
      } else {
        if (mode === "fast") {
          setMode("agent")
          toast.info("已选择工具能力，将使用智能体模式并展示实时执行轨迹")
        }
        const convId = await ensureConversation()
        const accepted = await sendAgentConversationMessage(convId, {
          content: question,
          tool_hints: toolHints,
          skip_tools: useRag ? [] : ["search_course_knowledge"],
        })
        const taskId = accepted.task.id
        setMessages((prev) => [
          ...prev,
          {
            id: `a-${taskId}`,
            kind: "agent",
            taskId,
            userQuestion: question,
            events: [],
            task: accepted.task,
            finalAnswer: "",
            streaming: true,
            error: null,
          },
        ])
        void watchAgentTask(taskId)
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "发送失败")
    } finally {
      setSending(false)
    }
  }

  const detailMessage = detailTarget
    ? messages.find((m) =>
        detailTarget.kind === "tutor"
          ? m.id === detailTarget.messageId
          : m.kind === "agent" && m.taskId === detailTarget.taskId,
      )
    : null
  const hasActiveStream = messages.some(
    (message) => message.kind !== "user" && Boolean(message.streaming),
  )

  return (
    <StudentShell title="AI 学习助手">
      <div className="mx-auto flex h-[calc(100dvh-7rem)] max-w-[1540px] flex-col gap-4 lg:flex-row">
        <section className="glass-card flex min-h-0 flex-1 flex-col overflow-hidden rounded-3xl">
          <div className="flex flex-wrap items-center gap-3 border-b border-white/60 bg-white/30 p-4">
            <ConversationHistoryHover
              courseId={courseId}
              conversationId={conversationId}
              onSelectConversation={applyConversation}
              onNewConversation={(id) => {
                stopVisibleStreams(true)
                setDetailTarget(null)
                setConversationId(id)
                localStorage.setItem(`${CONVERSATION_KEY}_${courseId}`, id)
                setMessages([])
              }}
            />
            <select
              value={courseId}
              onChange={(e) => setCourseId(e.target.value)}
              className="rounded-xl border border-white/80 bg-white/60 px-3 py-2 text-sm"
            >
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
            <select
              value={wikiPageId}
              onChange={(e) => setWikiPageId(e.target.value)}
              className="rounded-xl border border-white/80 bg-white/60 px-3 py-2 text-sm"
            >
              <option value="">Wiki 章节（可选）</option>
              {wikiPages.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title}
                </option>
              ))}
            </select>
            <ModeToggle
              mode={mode}
              onChange={(next) => {
                setMode(next)
                if (next === "fast") setToolHints([])
              }}
            />
            <label className="flex items-center gap-2 text-xs font-semibold text-outline">
              <input type="checkbox" checked={useRag} onChange={(e) => setUseRag(e.target.checked)} />
              资料库
            </label>
            <label className="flex items-center gap-2 text-xs font-semibold text-outline">
              <input type="checkbox" checked={useWiki} onChange={(e) => setUseWiki(e.target.checked)} />
              Wiki
            </label>
          </div>

          {mode === "agent" && (
            <div className="border-b border-white/60 px-4 py-3">
              <ToolSelector
                selected={toolHints}
                onChange={(tools) => {
                  setToolHints(tools)
                  if (tools.some((toolId) => AGENT_ONLY_TOOLS.has(toolId))) {
                    setMode("agent")
                  }
                }}
                disabled={sending}
              />
            </div>
          )}

          <div ref={listRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
            {!messages.length && (
              <div className="flex h-full flex-col items-center justify-center text-center text-outline">
                <span className="material-symbols-outlined mb-2 text-4xl text-primary/40">smart_toy</span>
                <p className="text-sm">选择模式后开始提问</p>
                <p className="mt-1 text-xs">流式过程可折叠查看，完成后回答直接展示在对话区</p>
              </div>
            )}
            {messages.map((msg) => {
              if (msg.kind === "user") {
                return (
                  <div key={msg.id} className="flex justify-end">
                    <div className="max-w-[80%] rounded-3xl rounded-tr-md bg-primary/10 px-4 py-3 text-sm">
                      {msg.content}
                    </div>
                  </div>
                )
              }
              if (msg.kind === "tutor") {
                const isStreaming = Boolean(msg.streaming)
                return (
                  <div key={msg.id} className="flex justify-start">
                    <TutorReplyBlock
                      content={msg.content}
                      progress={msg.progress}
                      streaming={isStreaming}
                      error={msg.error}
                      onOpenDetail={() => setDetailTarget({ kind: "tutor", messageId: msg.id })}
                    />
                  </div>
                )
              }
              const statusLabel = agentStatusLine(msg.events, msg.streaming)
              const toolCount = msg.task?.tool_call_count ?? 0
              const pendingMediaJobs = extractMediaJobProgress(msg.events)
              const mediaPending = pendingMediaJobs.length > 0
              const speechAudio = extractSpeechAudio(msg.events, msg.task)
              const chatArtifacts = extractChatArtifacts(msg.events, msg.task, msg.payloadArtifacts)
              const mediaArtifacts = extractChatMediaArtifacts(msg.events, msg.task, msg.payloadArtifacts)
              const canCancelAgentTask = msg.task
                ? !isTaskTerminal(msg.task.status)
                : msg.streaming || Boolean(msg.paused)
              return (
                <div key={msg.id} className="flex justify-start">
                  <AgentReplyBlock
                    statusLabel={statusLabel}
                    finalAnswer={msg.finalAnswer}
                    streaming={msg.streaming || mediaPending}
                    error={msg.error}
                    toolCount={toolCount}
                    events={msg.events}
                    paused={msg.paused}
                    speechAudio={speechAudio}
                    chatArtifacts={chatArtifacts}
                    mediaArtifacts={mediaArtifacts}
                    pendingMediaJobs={pendingMediaJobs}
                    onResume={msg.paused ? () => resumeAgentTaskView(msg.taskId) : undefined}
                    onCancel={canCancelAgentTask ? () => void cancelAgentTaskView(msg.taskId) : undefined}
                    onOpenDetail={() => setDetailTarget({ kind: "agent", taskId: msg.taskId })}
                  />
                </div>
              )
            })}
          </div>

          <div className="border-t border-white/60 p-4">
            <div className="flex gap-2">
              <Textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault()
                    void sendMessage()
                  }
                }}
                placeholder="输入问题，Enter 发送，Shift+Enter 换行"
                rows={2}
                className="min-h-[52px] flex-1 resize-none"
              />
              {hasActiveStream ? (
                <Button
                  type="button"
                  aria-label="停止生成"
                  title="停止生成"
                  onClick={() => stopVisibleStreams(true)}
                  className="h-[52px] w-[52px] shrink-0 rounded-full p-0"
                >
                  <span className="h-3 w-3 rounded-[3px] bg-current" aria-hidden="true" />
                </Button>
              ) : (
                <Button onClick={() => void sendMessage()} disabled={sending || !input.trim()}>
                  发送
                </Button>
              )}
            </div>
          </div>
        </section>

        <ResourceSidePanel
          courseId={courseId}
          wikiPageId={wikiPageId || null}
          refreshSignal={resourceRefreshSignal}
          highlightResourceType={resourceRevealType}
        />
      </div>

      {detailTarget?.kind === "tutor" && detailMessage?.kind === "tutor" && (
        <ActivityDetailDialog
          open
          onOpenChange={(open) => !open && setDetailTarget(null)}
          title="AI 回答详情"
          subtitle={detailMessage.progress || "快速模式"}
          content={detailMessage.content}
          streaming={detailMessage.streaming}
        />
      )}

      {detailTarget?.kind === "agent" && detailMessage?.kind === "agent" && (
        <ActivityDetailDialog
          open
          onOpenChange={(open) => !open && setDetailTarget(null)}
          title="智能体执行详情"
          subtitle={detailMessage.userQuestion || detailMessage.task?.task_goal}
          content={detailMessage.finalAnswer}
          streaming={detailMessage.streaming}
          events={detailMessage.events}
          task={detailMessage.task}
          error={detailMessage.error}
          onApprove={
            detailMessage.task?.status === "waiting_confirmation"
              ? (approved) => void approveAgentTask(detailMessage.taskId, approved)
              : undefined
          }
        />
      )}
    </StudentShell>
  )
}
