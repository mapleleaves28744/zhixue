"use client"

import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"
import { ResourceDetailDrawer } from "@/components/assistant/ResourceDetailDrawer"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { generateResource, getResource, listResources } from "@/services/resourceService"
import type { GeneratedResource, ResourceType } from "@/types/resource"

const RESOURCE_TYPES: { value: ResourceType; label: string }[] = [
  { value: "explanation", label: "讲解" },
  { value: "summary", label: "总结" },
  { value: "example", label: "例题" },
  { value: "flashcard", label: "复习卡" },
  { value: "review", label: "错题解析" },
  { value: "mindmap", label: "思维导图" },
  { value: "diagram", label: "图解" },
]

const LAST_RESOURCE_KEY = "zhixue_last_resource_id"

interface ResourceSidePanelProps {
  courseId: string
  wikiPageId?: string | null
}

export function ResourceSidePanel({ courseId, wikiPageId }: ResourceSidePanelProps) {
  const [resourceType, setResourceType] = useState<ResourceType>("explanation")
  const [requirement, setRequirement] = useState("")
  const [generating, setGenerating] = useState(false)
  const [history, setHistory] = useState<GeneratedResource[]>([])
  const [selected, setSelected] = useState<GeneratedResource | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)

  const loadHistory = useCallback(async (restoreLast = false) => {
    if (!courseId) return
    try {
      const data = await listResources({ courseId, page, pageSize: 20, status: "all" })
      setHistory(data.items)
      setTotal(data.total)

      const lastId = localStorage.getItem(`${LAST_RESOURCE_KEY}_${courseId}`)
      if (restoreLast && lastId) {
        try {
          const resource = await getResource(lastId)
          setSelected(resource)
        } catch {
          if (data.items[0]) setSelected(data.items[0])
        }
      } else if (restoreLast && data.items[0]) {
        setSelected(data.items[0])
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "加载资源历史失败")
    }
  }, [courseId, page])

  useEffect(() => {
    void loadHistory(true)
  }, [loadHistory])

  const handleGenerate = async () => {
    if (!courseId) {
      toast.error("请先选择课程")
      return
    }
    try {
      setGenerating(true)
      const result = await generateResource({
        course_id: courseId,
        wiki_page_id: wikiPageId ?? null,
        resource_type: resourceType,
        requirement: requirement || null,
        use_profile: true,
      })
      const resource: GeneratedResource = {
        id: result.id || result.resource_id,
        user_id: "",
        course_id: courseId,
        wiki_page_id: result.wiki_page_id,
        resource_type: result.resource_type,
        title: result.title,
        content: result.content,
        citations: result.citations,
        personalized_reason: result.personalized_reason,
        status: result.status,
        created_at: result.created_at || new Date().toISOString(),
      }
      localStorage.setItem(`${LAST_RESOURCE_KEY}_${courseId}`, resource.id)
      setSelected(resource)
      setDrawerOpen(true)
      toast.success("资源生成成功")
      await loadHistory(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "生成失败")
    } finally {
      setGenerating(false)
    }
  }

  const openResource = (resource: GeneratedResource) => {
    setSelected(resource)
    setDrawerOpen(true)
    localStorage.setItem(`${LAST_RESOURCE_KEY}_${courseId}`, resource.id)
  }

  return (
    <aside className="glass-card flex h-full w-full flex-col overflow-hidden rounded-3xl lg:w-[360px] lg:shrink-0">
      <div className="border-b border-white/60 p-4">
        <h2 className="text-sm font-bold text-on-surface">个性化资源</h2>
        <p className="mt-1 text-xs text-outline">生成后可从历史中随时找回</p>
      </div>

      <div className="space-y-3 overflow-y-auto p-4">
        <div className="flex flex-wrap gap-2">
          {RESOURCE_TYPES.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => setResourceType(t.value)}
              className={`rounded-full px-3 py-1 text-xs font-semibold ${
                resourceType === t.value
                  ? "bg-primary text-on-primary"
                  : "border border-white/80 bg-white/50 text-outline"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <Textarea
          value={requirement}
          onChange={(e) => setRequirement(e.target.value)}
          placeholder="例如：用适合初学者的方式解释，并给出一个小例题"
          className="min-h-[80px] resize-none"
        />
        <Button onClick={handleGenerate} disabled={generating} className="w-full">
          {generating ? "生成中…" : "生成资源"}
        </Button>

        <div className="pt-2">
          <p className="mb-2 text-xs font-bold text-outline">我的资源 ({total})</p>
          <div className="grid grid-cols-2 gap-2">
            {history.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => openResource(item)}
                className="flex h-24 flex-col items-start rounded-2xl border border-white/80 bg-white/50 p-3 text-left shadow-sm hover:border-primary/40"
              >
                <span className="material-symbols-outlined text-lg text-primary">description</span>
                <span className="mt-1 line-clamp-2 text-xs font-semibold">{item.title}</span>
                <span className="mt-auto text-[10px] text-outline">
                  {RESOURCE_TYPES.find((t) => t.value === item.resource_type)?.label || item.resource_type}
                </span>
              </button>
            ))}
          </div>
          {total > page * 20 && (
            <Button variant="outline" size="sm" className="mt-2 w-full" onClick={() => setPage((p) => p + 1)}>
              加载更多
            </Button>
          )}
        </div>
      </div>

      <ResourceDetailDrawer resource={selected} open={drawerOpen} onOpenChange={setDrawerOpen} />
    </aside>
  )
}
