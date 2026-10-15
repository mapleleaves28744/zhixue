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
  limit = 40,
): Promise<{ items: AgentMessage[] }> {
  return request<{ items: AgentMessage[] }>(
    `/api/v1/agent/conversations/${conversationId}/messages?limit=${encodeURIComponent(String(limit))}`,
  )
}

export function sendAgentConversationMessage(
  conversationId: string,
  payload: { content: string; client_request_id?: string; revises_task_id?: string; tool_hints?: string[]; skip_tools?: string[] },
): Promise<AgentMessageAccepted> {
  return request<AgentMessageAccepted>(
    `/api/v1/agent/conversations/${conversationId}/messages`,
    { method: "POST", body: payload },
  )
}

export function getAgentTask(taskId: string): Promise<AgentTask> {
  return request<AgentTask>(`/api/v1/agent/tasks/${taskId}`)
}

export async function prepareAgentTaskRevision(taskId: string, signal: AbortSignal): Promise<AgentTask> {
  let previous = await request<AgentTask>(`/api/v1/agent/tasks/${taskId}`, { signal })
  if (!["succeeded", "failed", "cancelled"].includes(previous.status)) {
    previous = await request<AgentTask>(`/api/v1/agent/tasks/${taskId}/cancel`, { method: "POST", signal })
  }
  const deadline = Date.now() + 300_000
  while (previous.execution_settled === false && Date.now() < deadline) {
    await new Promise<void>((resolve, reject) => {
      signal.throwIfAborted()
      const cancel = () => { clearTimeout(timer); reject(new DOMException("已取消", "AbortError")) }
      const timer = setTimeout(() => { signal.removeEventListener("abort", cancel); resolve() }, 1500)
      signal.addEventListener("abort", cancel, { once: true })
    })
    previous = await request<AgentTask>(`/api/v1/agent/tasks/${taskId}`, { signal })
  }
  signal.throwIfAborted()
  if (previous.execution_settled === false) throw new Error("原任务步骤尚未结束，请稍后重试修订")
  return previous
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
