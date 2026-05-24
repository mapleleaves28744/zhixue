"use client"

import { useEffect, useState } from "react"
import { WikiPageGrid } from "@/components/wiki/WikiPageGrid"
import { Button } from "@/components/ui/button"
import { listWikiPages } from "@/services/wikiService"
import type { WikiPageListItem } from "@/types/wiki"

export default function StudentWikiPage() {
  const [pages, setPages] = useState<WikiPageListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)

  // TODO: get courseId from context/route
  const courseId = "00000000-0000-0000-0000-000000000001"

  useEffect(() => {
    loadPages()
  }, [])

  const loadPages = async () => {
    try {
      setLoading(true)
      const data = await listWikiPages(courseId)
      setPages(data.items)
      setTotal(data.total)
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-6 p-6 md:p-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-headline-md text-headline-md text-on-surface">
            课程 Wiki
          </h1>
          <p className="font-body-md text-body-md text-on-surface-variant mt-1">
            {total > 0 ? `共 ${total} 个知识页面` : "从资料生成知识 Wiki，构建个人知识库"}
          </p>
        </div>
        <Button onClick={() => window.location.href = "/student/wiki/new"}>
          <span className="material-symbols-outlined text-[18px] mr-1">add</span>
          新建页面
        </Button>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-on-surface-variant">
          <span className="material-symbols-outlined text-[24px] animate-spin mr-2">
            sync
          </span>
          <span className="font-body-md">加载中...</span>
        </div>
      ) : (
        <WikiPageGrid pages={pages} />
      )}
    </div>
  )
}
