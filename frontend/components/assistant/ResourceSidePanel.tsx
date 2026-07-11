"use client"

import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"
import { ResourceDetailDrawer } from "@/components/assistant/ResourceDetailDrawer"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { getResourceTypeLabel, normalizeResourceType, RESOURCE_CATEGORY_OPTIONS } from "@/lib/resourceTypes"
import { generateResource, getResource, listResources } from "@/services/resourceService"
import type { GeneratedResource, ResourceType } from "@/types/resource"
import { cn } from "@/lib/utils"

const LAST_RESOURCE_KEY = "zhixue_last_resource_id"

export interface ResourceSidePanelProps {
  courseId: string
  className?: string
  wikiPageId?: string | null
  /** 递增时重新拉取资源列表（如 Agent 对话生成资源后） */
  refreshSignal?: number
  /** Agent 或桌宠跳转要求自动展开的资源分类 */
  highlightResourceType?: ResourceType | string | null
}

export function ResourceSidePanel({
  courseId,
  className,
  wikiPageId,
  refreshSignal = 0,
  highlightResourceType = null,
}: ResourceSidePanelProps) {
  const [resourceType, setResourceType] = useState<ResourceType>("explanation")
  const [requirement, setRequirement] = useState("")
  const [generating, setGenerating] = useState(false)
  const [history, setHistory] = useState<GeneratedResource[]>([])
  const [selected, setSelected] = useState<GeneratedResource | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [showingAllCourses, setShowingAllCourses] = useState(false)
  const [activeMediaJobId, setActiveMediaJobId] = useState<string | null>(null)

  const fetchPage = useCallback(
    async (targetPage: number, restoreLast = false, targetType: ResourceType = resourceType) => {
      if (!courseId) return
      try {
        let data = await listResources({
          courseId,
          resourceType: targetType,
          page: targetPage,
          pageSize: 20,
          status: "all",
        })
        if ((data.total ?? 0) === 0 && targetPage === 1) {
          const all = await listResources({
            resourceType: targetType,
            page: 1,
            pageSize: 20,
            status: "all",
          })
          if ((all.total ?? 0) > 0) {
            data = all
            setShowingAllCourses(true)
          } else {
            setShowingAllCourses(false)
          }
        } else {
          setShowingAllCourses(false)
        }
        setHistory(data.items)
        setTotal(data.total)

        const lastId = localStorage.getItem(`${LAST_RESOURCE_KEY}_${courseId}`)
        if (restoreLast && lastId) {
          try {
            const resource = await getResource(lastId)
            if ((normalizeResourceType(resource.resource_type) ?? resourceType) === targetType) {
              setSelected(resource)
            } else if (data.items[0]) {
              setSelected(data.items[0])
            }
          } catch {
            if (data.items[0]) setSelected(data.items[0])
          }
        } else if (restoreLast && data.items[0]) {
          setSelected(data.items[0])
        }
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "加载资源历史失败")
      }
    },
    [courseId, resourceType],
  )

  useEffect(() => {
    setPage(1)
    void fetchPage(1, true, resourceType)
  }, [fetchPage, resourceType])

  useEffect(() => {
    if (page === 1) return
    void fetchPage(page, false, resourceType)
  }, [page, fetchPage, resourceType])

  useEffect(() => {
    const routeType = normalizeResourceType(new URLSearchParams(window.location.search).get("resource_type"))
    if (routeType) setResourceType(routeType)
  }, [])

  useEffect(() => {
    if (!refreshSignal) return
    const nextType = normalizeResourceType(highlightResourceType)
    if (nextType && nextType !== resourceType) {
      setResourceType(nextType)
      setPage(1)
      void fetchPage(1, false, nextType)
      return
    }
    setPage(1)
    void fetchPage(1, false, resourceType)
  }, [refreshSignal, highlightResourceType, fetchPage, resourceType])

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
        media_asset_id: result.media_asset_id,
        media_mime_type: result.media_mime_type,
        media_asset_type: result.media_asset_type,
        media_file_url: result.media_file_url,
        content_format: result.content_format,
        preview_mode: result.preview_mode,
      }
      const nextType = normalizeResourceType(resource.resource_type) ?? resourceType
      localStorage.setItem(`${LAST_RESOURCE_KEY}_${courseId}`, resource.id)
      setResourceType(nextType)
      setPage(1)
      setSelected(resource)
      setActiveMediaJobId(result.media_job_id ?? null)
      setDrawerOpen(true)
      if (result.media_job_id) {
        toast.success(`已创建${getResourceTypeLabel(nextType)}任务，后台生成中…`)
      } else {
        toast.success(`资源生成成功，已放入「${getResourceTypeLabel(nextType)}」分类`)
      }
      await fetchPage(1, false, nextType)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "生成失败")
    } finally {
      setGenerating(false)
    }
  }

  const openResource = async (resource: GeneratedResource) => {
    try {
      const detail = await getResource(resource.id)
      setSelected(detail)
      setActiveMediaJobId(detail.media_job_id && !detail.media_asset_id ? detail.media_job_id : null)
      setDrawerOpen(true)
      localStorage.setItem(`${LAST_RESOURCE_KEY}_${courseId}`, resource.id)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "加载资源详情失败")
    }
  }

  return (
    <aside className={cn("glass-card flex min-h-0 w-full flex-col overflow-hidden rounded-3xl", className)}>
      <div className="border-b border-white/60 p-4">
        <h2 className="text-sm font-bold text-on-surface">个性化资源</h2>
        <p className="mt-1 text-xs text-outline">按类型收纳，生成后自动定位到对应分类</p>
      </div>

      <div className="space-y-3 overflow-y-auto p-4">
        <div className="flex flex-wrap gap-2">
          {RESOURCE_CATEGORY_OPTIONS.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => {
                setPage(1)
                setResourceType(t.value)
              }}
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
          <p className="mb-2 text-xs font-bold text-outline">
            我的「{getResourceTypeLabel(resourceType)}」资源 ({total})
            {showingAllCourses ? (
              <span className="ml-1 font-normal text-primary">· 已显示全部课程</span>
            ) : null}
          </p>
          <div className="grid grid-cols-2 gap-2">
            {history.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => openResource(item)}
                className="flex h-24 flex-col items-start rounded-2xl border border-white/80 bg-white/50 p-3 text-left shadow-sm hover:border-primary/40"
              >
                <span className="material-symbols-outlined text-lg text-primary">
                  {item.preview_mode === "audio"
                    ? "volume_up"
                    : item.preview_mode === "video"
                      ? "movie"
                      : item.preview_mode === "image" || ["image", "mindmap", "diagram"].includes(String(item.resource_type))
                        ? "image"
                        : item.preview_mode === "mermaid" || ["mindmap", "diagram"].includes(String(item.resource_type))
                          ? "account_tree"
                          : item.resource_type === "interactive_courseware" || item.resource_type === "immersive_classroom"
                            ? "view_in_ar"
                            : item.resource_type === "code_project"
                              ? "code_blocks"
                              : item.resource_type === "flashcard"
                                ? "style"
                                : item.resource_type === "review"
                                  ? "assignment_late"
                                  : "description"}
                </span>
                <span className="mt-1 line-clamp-2 text-xs font-semibold">{item.title}</span>
                <span className="mt-auto text-[10px] text-outline">{getResourceTypeLabel(item.resource_type)}</span>
              </button>
            ))}
          </div>
          {!history.length && (
            <div className="rounded-2xl border border-dashed border-primary/30 bg-white/40 p-4 text-xs text-outline">
              当前还没有「{getResourceTypeLabel(resourceType)}」资源。你可以先在上方输入要求生成，也可以在智能体对话中调用对应工具。
            </div>
          )}
          {total > page * 20 && (
            <Button variant="outline" size="sm" className="mt-2 w-full" onClick={() => setPage((p) => p + 1)}>
              加载更多
            </Button>
          )}
        </div>
      </div>

      <ResourceDetailDrawer
        resource={selected}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        mediaJobId={activeMediaJobId}
        onResourceUpdated={(resource) => {
          setSelected(resource)
          setActiveMediaJobId(null)
        }}
      />
    </aside>
  )
}
