export interface AgentConversation {
  id: string
  user_id: string
  course_id: string | null
  thread_id: string
  title: string
  status: string
  summary?: string | null
  extra_meta: Record<string, unknown>
  last_message_at?: string | null
  created_at: string
  updated_at: string
}

export interface AgentMessage {
  id: string
  conversation_id: string
  user_id: string
  task_id?: string | null
  role: string
  message_type: string
  content: string
  payload: Record<string, unknown>
  created_at: string
}

export interface AgentTask {
  id: string
  user_id: string
  course_id: string
  conversation_id: string
  thread_id: string
  task_goal: string
  task_type: string
  status: string
  runtime_mode: string
  plan_json: Record<string, unknown>
  risk_level: string
  requires_confirmation: boolean
  iteration_count: number
  tool_call_count: number
  replan_count: number
  error_message?: string | null
  created_at: string
  updated_at: string
}

export interface AgentMessageAccepted {
  conversation: AgentConversation
  message: AgentMessage
  task: AgentTask
  queued: boolean
}

export interface AgentTaskEvent {
  type: string
  data: Record<string, unknown>
}

export type AssistantMode = "fast" | "agent"

export const TOOL_OPTIONS = [
  { id: "search_course_knowledge", label: "搜索知识库" },
  { id: "generate_quiz", label: "生成练习" },
  { id: "generate_learning_resource", label: "生成资源" },
  { id: "update_profile_from_dialogue", label: "更新画像" },
  { id: "answer_course_question", label: "课程答疑" },
  { id: "synthesize_speech", label: "语音讲解" },
] as const
