import { request } from "@/lib/request"
import type {
  TutorChatRequest,
  TutorChatResponse,
  TutorFeedbackRequest,
  TutorSaveToWikiRequest,
} from "@/types/tutor"

export function chatWithTutor(payload: TutorChatRequest): Promise<TutorChatResponse> {
  return request<TutorChatResponse>("/tutor/chat", {
    method: "POST",
    body: payload,
  })
}

export function saveTutorAnswerToWiki(
  messageId: string,
  payload: TutorSaveToWikiRequest,
): Promise<{ message_id: string; wiki_page: { id: string; title: string; current_version: number } }> {
  return request(`/tutor/messages/${messageId}/save-to-wiki`, {
    method: "POST",
    body: payload,
  })
}

export function submitTutorFeedback(
  messageId: string,
  payload: TutorFeedbackRequest,
): Promise<{ feedback_id: string; message_id: string; feedback_type: string }> {
  return request(`/tutor/messages/${messageId}/feedback`, {
    method: "POST",
    body: payload,
  })
}
