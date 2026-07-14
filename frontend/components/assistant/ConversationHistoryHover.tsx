"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { cn } from "@/lib/utils"
import type { AgentConversation, AgentMessage } from "@/types/agent"
import type { GeneratedResource } from "@/types/resource"
import type { ResourceType } from "@/types/resource"
import {
  createAgentConversation,
  listAgentConversationMessages,
  listAgentConversations,
} from "@/services/agentService"
import { listResources } from "@/services/resourceService"
import { getResourceTypeLabel, normalizeResourceType } from "@/lib/resourceTypes"

interface ConversationHistoryHoverProps {
  courseId: string
  conversationId: string | null
  onSelectConversation: (conversationId: string, messages: AgentMessage[]) => void
  onNewConversation: (conversationId: string) => void
  onOpenResources: (resourceType: ResourceType | null) => void
}

export function ConversationHistoryHover({
  courseId,
  conversationId,
  onSelectConversation,
  onNewConversation,
  onOpenResources,
}: ConversationHistoryHoverProps) {
  const [open, setOpen] = useState(false)
  const [conversations, setConversations] = useState<AgentConversation[]>([])
  const [resources, setResources] = useState<GeneratedResource[]>([])
  const [activeTab, setActiveTab] = useState<"conversations" | "resources">("conversations")
  const [query, setQuery] = useState("")
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    if (!courseId) return
    setLoading(true)
    try {
      const [conversationData, resourceData] = await Promise.all([
        listAgentConversations(),
        listResources({ courseId, page: 1, pageSize: 100, status: "all" }),
      ])
      const filtered = conversationData.items
        .filter((c) => c.course_id === courseId)
        .sort((a, b) => {
          const ta = new Date(a.last_message_at || a.updated_at).getTime()
          const tb = new Date(b.last_message_at || b.updated_at).getTime()
          return tb - ta
        })
      setConversations(filtered)
      setResources(resourceData.items)
    } catch {
      setConversations([])
      setResources([])
    } finally {
      setLoading(false)
    }
  }, [courseId])

  useEffect(() => {
    if (open) void load()
  }, [open, load])

  useEffect(() => {
    if (!open) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false)
    }
    window.addEventListener("keydown", closeOnEscape)
    return () => window.removeEventListener("keydown", closeOnEscape)
  }, [open])

  const normalizedQuery = query.trim().toLowerCase()
  const filteredConversations = useMemo(
    () =>
      conversations.filter((conversation) =>
        `${conversation.title} ${conversation.summary || ""}`.toLowerCase().includes(normalizedQuery),
      ),
    [conversations, normalizedQuery],
  )
  const filteredResources = useMemo(
    () =>
      resources.filter((resource) =>
        `${resource.title} ${resource.resource_type}`.toLowerCase().includes(normalizedQuery),
      ),
    [resources, normalizedQuery],
  )

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
    <div className="relative">
      <button
        type="button"
        aria-label="学习记录"
        aria-expanded={open}
        aria-controls="assistant-learning-records"
        onClick={() => setOpen((value) => !value)}
        className={cn(
          "flex h-10 w-10 items-center justify-center rounded-xl border border-white/80 bg-white/60 text-outline transition hover:text-primary",
          open && "border-primary/30 text-primary bg-white/90",
        )}
      >
        <span className="material-symbols-outlined text-[20px]">history</span>
      </button>

      {open && (
        <div
          id="assistant-learning-records"
          role="dialog"
          aria-label="学习记录"
          className="absolute left-0 top-full z-50 mt-2 w-[min(24rem,calc(100vw-2rem))] rounded-2xl border border-white/80 bg-[#fcf9f8]/95 p-3 shadow-xl backdrop-blur-xl"
        >
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-bold text-on-surface">学习记录</p>
              <p className="mt-0.5 text-[11px] text-outline">当前课程 · 对话和生成资源统一查看</p>
            </div>
            <button
              type="button"
              aria-label="关闭学习记录"
              onClick={() => setOpen(false)}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-outline transition hover:bg-white/80 hover:text-primary"
            >
              <span className="material-symbols-outlined text-[18px]">close</span>
            </button>
          </div>

          <div className="mt-3 grid grid-cols-2 rounded-xl bg-white/55 p-1" role="tablist" aria-label="学习记录分类">
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "conversations"}
              onClick={() => setActiveTab("conversations")}
              className={cn(
                "rounded-lg px-2 py-1.5 text-xs font-semibold transition",
                activeTab === "conversations" ? "bg-white text-primary shadow-sm" : "text-outline hover:text-primary",
              )}
            >
              对话 ({conversations.length})
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "resources"}
              onClick={() => setActiveTab("resources")}
              className={cn(
                "rounded-lg px-2 py-1.5 text-xs font-semibold transition",
                activeTab === "resources" ? "bg-white text-primary shadow-sm" : "text-outline hover:text-primary",
              )}
            >
              已生成 ({resources.length})
            </button>
          </div>

          <div className="mt-3 flex gap-2">
            <label className="flex min-w-0 flex-1 items-center gap-1.5 rounded-xl border border-white/90 bg-white/70 px-2.5 py-2 text-outline focus-within:border-primary/40">
              <span className="material-symbols-outlined text-[16px]">search</span>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={activeTab === "conversations" ? "搜索对话标题" : "搜索资源标题"}
                className="min-w-0 flex-1 bg-transparent text-xs text-on-surface outline-none placeholder:text-outline"
              />
            </label>
            {activeTab === "conversations" ? (
              <button
                type="button"
                onClick={() => void startNew()}
                className="rounded-xl bg-primary/10 px-3 text-xs font-semibold text-primary transition hover:bg-primary/15"
              >
                新对话
              </button>
            ) : null}
          </div>

          {loading ? (
            <p className="py-4 text-center text-xs text-outline">加载中…</p>
          ) : (
            <div className="mt-3 max-h-[min(56dvh,390px)] space-y-1.5 overflow-y-auto pr-1">
              {activeTab === "conversations" ? (
                filteredConversations.length ? (
                  filteredConversations.map((conv) => (
                    <button
                      key={conv.id}
                      type="button"
                      onClick={() => void selectConversation(conv.id)}
                      className={cn(
                        "w-full rounded-xl border border-transparent px-3 py-2.5 text-left text-xs transition hover:border-primary/20 hover:bg-white/80",
                        conv.id === conversationId
                          ? "border-primary/20 bg-primary/10 text-primary"
                          : "text-on-surface-variant",
                      )}
                    >
                      <span className="flex items-center gap-2">
                        <span className="block min-w-0 flex-1 truncate font-semibold">{conv.title || "未命名对话"}</span>
                        {conv.id === conversationId ? <span className="text-[10px] font-semibold">当前</span> : null}
                      </span>
                      <span className="mt-1 block text-[10px] text-outline">
                        {new Date(conv.last_message_at || conv.updated_at).toLocaleString()}
                      </span>
                    </button>
                  ))
                ) : (
                  <p className="py-6 text-center text-xs text-outline">
                    {query ? "没有匹配的对话" : "本课程暂时没有对话记录"}
                  </p>
                )
              ) : filteredResources.length ? (
                filteredResources.map((resource) => {
                  return (
                    <button
                      key={resource.id}
                      type="button"
                      onClick={() => {
                        onOpenResources(normalizeResourceType(resource.resource_type))
                        setOpen(false)
                      }}
                      className="w-full rounded-xl border border-transparent bg-white/45 px-3 py-2.5 text-left transition hover:border-primary/20 hover:bg-white/80"
                    >
                      <span className="flex items-center gap-2">
                        <span className="material-symbols-outlined text-[18px] text-primary">auto_stories</span>
                        <span className="min-w-0 flex-1 truncate text-xs font-semibold text-on-surface">{resource.title}</span>
                      </span>
                      <span className="mt-1 block text-[10px] text-outline">
                        {getResourceTypeLabel(resource.resource_type)} · {new Date(resource.created_at).toLocaleString()}
                      </span>
                    </button>
                  )
                })
              ) : (
                <p className="py-6 text-center text-xs text-outline">
                  {query ? "没有匹配的资源" : "本课程暂时没有生成资源"}
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
