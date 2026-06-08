import { buildApiUrl } from "@/lib/api"
import { getToken } from "@/lib/auth"
import { request } from "@/lib/request"
import { consumeSseStream } from "@/lib/sse"
import type {
  TutorChatRequest,
  TutorChatResponse,
  TutorFeedbackRequest,
  TutorSaveToWikiRequest,
} from "@/types/tutor"

export function chatWithTutor(payload: TutorChatRequest): Promise<TutorChatResponse> {
  return request<TutorChatResponse>("/api/v1/tutor/chat", {
    method: "POST",
    body: payload,
  })
}

export type TutorStreamHandlers = {
  onOpen?: () => void
  onClose?: () => void
  onProgress?: (data: { stage?: string; message?: string }) => void
  onDelta?: (content: string) => void
  onDone?: (data: TutorChatResponse) => void
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

  try {
    await consumeSseStream(
      "/api/v1/tutor/chat",
      {
        onOpen: handlers.onOpen,
        onClose: handlers.onClose,
        onEvent: (eventName, data) => {
          if (eventName === "delta") {
            handlers.onDelta?.(String(data.content || ""))
          } else if (eventName === "progress") {
            handlers.onProgress?.({
              stage: String(data.stage || ""),
              message: String(data.message || ""),
            })
          } else if (eventName === "done") {
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
  } catch (error) {
    const fallback = await chatWithTutor(payload)
    if (fallback.answer) handlers.onDelta?.(fallback.answer)
    handlers.onDone?.(fallback)
    return fallback
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
