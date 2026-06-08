"use client"

import { useCallback, useEffect, useState } from "react"
import { cn } from "@/lib/utils"
import type { AgentConversation, AgentMessage } from "@/types/agent"
import {
  createAgentConversation,
  listAgentConversationMessages,
  listAgentConversations,
} from "@/services/agentService"

interface ConversationHistoryHoverProps {
  courseId: string
  conversationId: string | null
  onSelectConversation: (conversationId: string, messages: AgentMessage[]) => void
  onNewConversation: (conversationId: string) => void
}

export function ConversationHistoryHover({
  courseId,
  conversationId,
  onSelectConversation,
  onNewConversation,
}: ConversationHistoryHoverProps) {
  const [open, setOpen] = useState(false)
  const [conversations, setConversations] = useState<AgentConversation[]>([])
  const [recentMessages, setRecentMessages] = useState<AgentMessage[]>([])
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    if (!courseId) return
    setLoading(true)
    try {
      const { items } = await listAgentConversations()
      const filtered = items
        .filter((c) => c.course_id === courseId)
        .sort((a, b) => {
          const ta = new Date(a.last_message_at || a.updated_at).getTime()
          const tb = new Date(b.last_message_at || b.updated_at).getTime()
          return tb - ta
        })
      setConversations(filtered.slice(0, 12))
      if (conversationId) {
        const msgs = await listAgentConversationMessages(conversationId)
        setRecentMessages(msgs.items.slice(-8).reverse())
      } else {
        setRecentMessages([])
      }
    } catch {
      setConversations([])
      setRecentMessages([])
    } finally {
      setLoading(false)
    }
  }, [courseId, conversationId])

  useEffect(() => {
    if (open) void load()
  }, [open, load])

  const selectConversation = async (id: string) => {
    try {
      const { items } = await listAgentConversationMessages(id)
      onSelectConversation(id, items)
      setOpen(false)
    } catch {
      /* ignore */
    }
  }

  const startNew = async () => {
    if (!courseId) return
    try {
      const conv = await createAgentConversation({ course_id: courseId, title: "新对话" })
      onNewConversation(conv.id)
      setOpen(false)
    } catch {
      /* ignore */
    }
  }

  return (
    <div
      className="relative"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        aria-label="对话历史"
        className={cn(
          "flex h-10 w-10 items-center justify-center rounded-xl border border-white/80 bg-white/60 text-outline transition hover:text-primary",
          open && "border-primary/30 text-primary bg-white/90",
        )}
      >
        <span className="material-symbols-outlined text-[20px]">history</span>
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 w-80 rounded-2xl border border-white/80 bg-[#fcf9f8]/95 p-3 shadow-xl backdrop-blur-xl">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs font-bold text-on-surface">对话历史</p>
            <button
              type="button"
              onClick={() => void startNew()}
              className="text-xs font-semibold text-primary hover:underline"
            >
              新对话
            </button>
          </div>

          {loading ? (
            <p className="py-4 text-center text-xs text-outline">加载中…</p>
          ) : (
            <>
              {recentMessages.length > 0 && (
                <div className="mb-3">
                  <p className="mb-1 text-[10px] font-bold uppercase text-outline">当前会话</p>
                  <div className="max-h-32 space-y-1 overflow-y-auto">
                    {recentMessages.map((m) => (
                      <div
                        key={m.id}
                        className="truncate rounded-lg bg-white/70 px-2 py-1.5 text-xs text-on-surface-variant"
                        title={m.content}
                      >
                        <span className="font-semibold text-primary">
                          {m.role === "user" ? "你" : "AI"}：
                        </span>
                        {m.content.slice(0, 48)}
                        {m.content.length > 48 ? "…" : ""}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <p className="mb-1 text-[10px] font-bold uppercase text-outline">历史会话</p>
              <div className="max-h-48 space-y-1 overflow-y-auto">
                {conversations.length ? (
                  conversations.map((conv) => (
                    <button
                      key={conv.id}
                      type="button"
                      onClick={() => void selectConversation(conv.id)}
                      className={cn(
                        "w-full rounded-xl px-3 py-2 text-left text-xs transition hover:bg-white/80",
                        conv.id === conversationId
                          ? "bg-primary/10 text-primary"
                          : "text-on-surface-variant",
                      )}
                    >
                      <span className="block truncate font-semibold">
                        {conv.title || "未命名对话"}
                      </span>
                      <span className="text-[10px] text-outline">
                        {new Date(conv.last_message_at || conv.updated_at).toLocaleString()}
                      </span>
                    </button>
                  ))
                ) : (
                  <p className="py-3 text-center text-xs text-outline">暂无历史会话</p>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
