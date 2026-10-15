import { buildApiUrl } from "@/lib/api"
import { getToken } from "@/lib/auth"
import { request } from "@/lib/request"
import { RequestError } from "@/lib/request"
import { consumeSseStream } from "@/lib/sse"
import type {
  TutorChatRequest,
  TutorChatResponse,
  TutorFeedbackRequest,
  TutorSaveToWikiRequest,
} from "@/types/tutor"

export function chatWithTutor(
  payload: TutorChatRequest,
  signal?: AbortSignal,
): Promise<TutorChatResponse> {
  return request<TutorChatResponse>("/api/v1/tutor/chat", {
    method: "POST",
    body: payload,
    signal,
  })
}

export function getTutorRequestStatus(
  conversationId: string,
  clientRequestId: string,
  signal?: AbortSignal,
): Promise<{ status: string; response: TutorChatResponse | null; error_message: string | null }> {
  return request(`/api/v1/tutor/conversations/${conversationId}/requests/${clientRequestId}`, { signal })
}

export type TutorStreamHandlers = {
  onOpen?: () => void
  onClose?: () => void
  onProgress?: (data: { stage?: string; message?: string }) => void
  onEvidence?: (
    data: Pick<TutorChatResponse, "grounding_status" | "grounding_message" | "citations">,
  ) => void
  onDelta?: (content: string) => void
  onDone?: (data: TutorChatResponse) => void
  onInterrupted?: (error: Error) => void
  signal?: AbortSignal
}

export async function streamTutorChat(
  payload: TutorChatRequest,
  handlers: TutorStreamHandlers,
): Promise<TutorChatResponse | null> {
  const token = getToken()
  if (!token) {
    throw new Error("请先登录后再操作")
  }

  let finalPayload: TutorChatResponse | null = null
  let receivedDelta = false
  let receivedDone = false
  let fallbackAttempted = false

  const awaitCommittedResult = async (): Promise<TutorChatResponse | null> => {
    if (!payload.conversation_id || !payload.client_request_id) return null
    for (let attempt = 0; attempt < 15 && !handlers.signal?.aborted; attempt += 1) {
      try {
        const state = await getTutorRequestStatus(payload.conversation_id, payload.client_request_id, handlers.signal)
        if (state.status === "succeeded" && state.response) {
          handlers.onDone?.(state.response)
          return state.response
        }
        if (state.status === "failed") return null
      } catch (error) {
        if (error instanceof RequestError && error.status === 404) return null
      }
      await new Promise<void>((resolve) => setTimeout(resolve, 1000))
    }
    return null
  }

  const runFallback = async (): Promise<TutorChatResponse | null> => {
    if (handlers.signal?.aborted) return finalPayload
    fallbackAttempted = true
    const committed = await awaitCommittedResult()
    if (committed) return committed
    if (handlers.signal?.aborted) return finalPayload
    const fallback = await chatWithTutor({ ...payload, stream: false }, handlers.signal)
    if (handlers.signal?.aborted) return finalPayload
    handlers.onDone?.(fallback)
    return fallback
  }

  try {
    await consumeSseStream(
      "/api/v1/tutor/chat",
      {
        onOpen: handlers.onOpen,
        onClose: handlers.onClose,
        signal: handlers.signal,
        onEvent: (eventName, data) => {
          if (eventName === "delta") {
            const content = String(data.content || "")
            if (content) receivedDelta = true
            handlers.onDelta?.(content)
          } else if (eventName === "evidence") {
            handlers.onEvidence?.(
              data as unknown as Pick<
                TutorChatResponse,
                "grounding_status" | "grounding_message" | "citations"
              >,
            )
          } else if (eventName === "progress") {
            handlers.onProgress?.({
              stage: String(data.stage || ""),
              message: String(data.message || ""),
            })
          } else if (eventName === "done") {
            receivedDone = true
            finalPayload = data as unknown as TutorChatResponse
            handlers.onDone?.(finalPayload)
          } else if (eventName === "error") {
            throw new Error(String(data.message || "AI Tutor 请求失败"))
          }
        },
      },
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...payload, stream: true }),
      },
    )
    if (!receivedDone) {
      const eofError = new Error("AI Tutor 流式连接提前结束")
      if (!receivedDelta) return await runFallback()
      const committed = await awaitCommittedResult()
      if (committed) return committed
      handlers.onInterrupted?.(eofError)
      return finalPayload
    }
  } catch (error) {
    if (receivedDone) return finalPayload
    if (handlers.signal?.aborted) {
      return finalPayload
    }
    const streamError = error instanceof Error ? error : new Error("AI Tutor 流式请求失败")
    if (fallbackAttempted) throw streamError
    if (!receivedDelta) {
      return await runFallback()
    }
    const committed = await awaitCommittedResult()
    if (committed) return committed
    handlers.onInterrupted?.(streamError)
    return finalPayload
  }

  return finalPayload
}

export function saveTutorAnswerToWiki(
  messageId: string,
  payload: TutorSaveToWikiRequest,
): Promise<{ message_id: string; wiki_page: { id: string; title: string; current_version: number } }> {
  return request(`/api/v1/tutor/messages/${messageId}/save-to-wiki`, {
    method: "POST",
    body: payload,
  })
}

export function submitTutorFeedback(
  messageId: string,
  payload: TutorFeedbackRequest,
): Promise<{ feedback_id: string; message_id: string; feedback_type: string }> {
  return request(`/api/v1/tutor/messages/${messageId}/feedback`, {
    method: "POST",
    body: payload,
  })
}
