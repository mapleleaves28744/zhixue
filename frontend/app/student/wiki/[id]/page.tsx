"use client"

import { useParams, useRouter } from "next/navigation"
import { useCallback, useEffect, useState } from "react"
import { WikiContentRenderer } from "@/components/wiki/WikiContentRenderer"
import { WikiEditor } from "@/components/wiki/WikiEditor"
import { WikiSourcePanel } from "@/components/wiki/WikiSourcePanel"
import { WikiVersionHistory } from "@/components/wiki/WikiVersionHistory"
import { ResourceGenerateDialog } from "@/components/resources/ResourceGenerateDialog"
import { Button } from "@/components/ui/button"
import { getWikiPage, updateWikiPage } from "@/services/wikiService"
import type { WikiPage } from "@/types/wiki"

export default function WikiDetailPage() {
  const params = useParams()
  const router = useRouter()
  const pageId = params.id as string

  const [page, setPage] = useState<WikiPage | null>(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [showVersions, setShowVersions] = useState(false)
  const [showResourceDialog, setShowResourceDialog] = useState(false)

  const loadPage = useCallback(async () => {
    try {
      setLoading(true)
      const data = await getWikiPage(pageId)
      setPage(data)
    } catch {
      router.push("/student/wiki")
    } finally {
      setLoading(false)
    }
  }, [pageId, router])

  useEffect(() => {
    loadPage()
  }, [loadPage])

  const handleSave = async (data: {
    title: string
    content: string
    summary: string
    changeMessage: string
  }) => {
    await updateWikiPage(pageId, {
      title: data.title,
      content: data.content,
      summary: data.summary,
      changeMessage: data.changeMessage,
    })
    setEditing(false)
    await loadPage()
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-on-surface-variant">
        <span className="material-symbols-outlined text-[24px] animate-spin mr-2">
          sync
        </span>
        <span className="font-body-md">加载中...</span>
      </div>
    )
  }

  if (!page) return null

  if (editing) {
    return (
      <div className="p-6 md:p-8 h-full">
        <WikiEditor
          initialTitle={page.title}
          initialContent={page.content}
          initialSummary={page.summary ?? ""}
          onSave={handleSave}
          onCancel={() => setEditing(false)}
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <div className="flex items-center justify-between px-6 md:px-8 py-4 border-b border-outline-variant/20">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push("/student/wiki")}
            className="text-on-surface-variant hover:text-primary transition-colors"
          >
            <span className="material-symbols-outlined">arrow_back</span>
          </button>
          <div>
            <h1 className="font-headline-md text-headline-md text-on-surface">
              {page.title}
            </h1>
            <p className="font-body-md text-xs text-on-surface-variant mt-0.5">
              v{page.current_version} ·{" "}
              {new Date(page.updated_at).toLocaleString("zh-CN")}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowVersions(!showVersions)}
          >
            <span className="material-symbols-outlined text-[16px] mr-1">
              history
            </span>
            版本
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowResourceDialog(true)}
          >
            <span className="material-symbols-outlined text-[16px] mr-1">
              auto_awesome
            </span>
            生成资源
          </Button>
          <Button size="sm" onClick={() => setEditing(true)}>
            <span className="material-symbols-outlined text-[16px] mr-1">
              edit
            </span>
            编辑
          </Button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Content area */}
        <div className="flex-1 overflow-y-auto px-6 md:px-8 py-6">
          {page.summary && (
            <div className="glass-card p-4 mb-6 bg-primary/5 border-primary/10">
              <p className="font-body-md text-sm text-on-surface-variant">
                <span className="font-label-md text-primary mr-2">摘要</span>
                {page.summary}
              </p>
            </div>
          )}
          <WikiContentRenderer content={page.content} />
        </div>

        {/* Right sidebar */}
        <div className="w-72 border-l border-outline-variant/20 overflow-y-auto p-4 flex flex-col gap-6 hidden lg:flex">
          {showVersions ? (
            <WikiVersionHistory
              pageId={pageId}
              currentVersion={page.current_version}
              onRollback={loadPage}
            />
          ) : (
            <WikiSourcePanel sources={page.sources ?? []} />
          )}
        </div>
      </div>

      {/* Resource generation dialog */}
      <ResourceGenerateDialog
        open={showResourceDialog}
        onOpenChange={setShowResourceDialog}
        courseId={page.course_id}
        wikiPageId={pageId}
        wikiPageTitle={page.title}
        onSaved={loadPage}
      />
    </div>
  )
}
