import { consumeSseStream } from "@/lib/sse"
import { request } from "@/lib/request"
import type {
  AgentConversation,
  AgentMessage,
  AgentMessageAccepted,
  AgentTask,
} from "@/types/agent"

export function createAgentConversation(payload: {
  course_id: string
  title?: string | null
}): Promise<AgentConversation> {
  return request<AgentConversation>("/api/v1/agent/conversations", {
    method: "POST",
    body: payload,
  })
}

export function listAgentConversations(): Promise<{ items: AgentConversation[] }> {
  return request<{ items: AgentConversation[] }>("/api/v1/agent/conversations")
}

export function listAgentConversationMessages(
  conversationId: string,
): Promise<{ items: AgentMessage[] }> {
  return request<{ items: AgentMessage[] }>(
    `/api/v1/agent/conversations/${conversationId}/messages`,
  )
}

export function sendAgentConversationMessage(
  conversationId: string,
  payload: { content: string; tool_hints?: string[]; skip_tools?: string[] },
): Promise<AgentMessageAccepted> {
  return request<AgentMessageAccepted>(
    `/api/v1/agent/conversations/${conversationId}/messages`,
    { method: "POST", body: payload },
  )
}

export function getAgentTask(taskId: string): Promise<AgentTask> {
  return request<AgentTask>(`/api/v1/agent/tasks/${taskId}`)
}

export function listAgentTaskEvents(
  taskId: string,
): Promise<{ items: Array<{ event_type: string; payload: Record<string, unknown> }> }> {
  return request<{ items: Array<{ event_type: string; payload: Record<string, unknown> }> }>(
    `/api/v1/agent/tasks/${taskId}/events/history`,
  )
}

export function resumeAgentTask(taskId: string, approved = true): Promise<AgentTask> {
  return request<AgentTask>(`/api/v1/agent/tasks/${taskId}/resume`, {
    method: "POST",
    body: { approved },
  })
}

export function cancelAgentTask(taskId: string): Promise<AgentTask> {
  return request<AgentTask>(`/api/v1/agent/tasks/${taskId}/cancel`, { method: "POST" })
}

export function requeueAgentTask(taskId: string): Promise<AgentTask> {
  return request<AgentTask>(`/api/v1/agent/tasks/${taskId}/requeue`, { method: "POST" })
}

export function streamAgentTaskEvents(
  taskId: string,
  handlers: {
    onEvent?: (eventType: string, data: Record<string, unknown>) => void
    onOpen?: () => void
    onClose?: () => void
    signal?: AbortSignal
  },
): Promise<void> {
  return consumeSseStream(`/api/v1/agent/tasks/${taskId}/events`, {
    onOpen: handlers.onOpen,
    onClose: handlers.onClose,
    onEvent: handlers.onEvent,
    signal: handlers.signal,
  })
}
