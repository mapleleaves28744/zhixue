"use client"

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { listWikiVersions, rollbackWikiVersion } from "@/services/wikiService"
import type { WikiPageVersion } from "@/types/wiki"

interface WikiVersionHistoryProps {
  pageId: string
  currentVersion: number
  onRollback?: () => void
}

export function WikiVersionHistory({
  pageId,
  currentVersion,
  onRollback,
}: WikiVersionHistoryProps) {
  const [versions, setVersions] = useState<WikiPageVersion[]>([])
  const [loading, setLoading] = useState(true)
  const [rollingBack, setRollingBack] = useState<number | null>(null)

  useEffect(() => {
    loadVersions()
  }, [pageId])

  const loadVersions = async () => {
    try {
      setLoading(true)
      const data = await listWikiVersions(pageId)
      setVersions(data)
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }

  const handleRollback = async (versionNumber: number) => {
    try {
      setRollingBack(versionNumber)
      await rollbackWikiVersion(pageId, versionNumber)
      await loadVersions()
      onRollback?.()
    } catch {
      // silent
    } finally {
      setRollingBack(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-4 text-on-surface-variant">
        <span className="material-symbols-outlined text-[18px] animate-spin">sync</span>
        <span className="font-body-md text-sm">加载版本历史...</span>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <h4 className="font-label-md text-label-md text-on-surface flex items-center gap-2">
        <span className="material-symbols-outlined text-[18px] text-primary">history</span>
        版本历史
      </h4>
      <div className="flex flex-col gap-2 max-h-[400px] overflow-y-auto pr-1">
        {versions.map((v) => (
          <div
            key={v.id}
            className={`glass-card p-3 flex items-center justify-between gap-3 ${
              v.version_number === currentVersion ? "border-primary/30 bg-primary/5" : ""
            }`}
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-label-md text-sm text-on-surface">
                  v{v.version_number}
                </span>
                {v.version_number === currentVersion && (
                  <span className="px-1.5 py-0.5 rounded bg-primary/10 text-primary font-label-sm text-[10px]">
                    当前
                  </span>
                )}
              </div>
              {v.change_message && (
                <p className="font-body-md text-xs text-on-surface-variant truncate mt-0.5">
                  {v.change_message}
                </p>
              )}
              <p className="font-body-md text-[11px] text-on-surface-variant/60 mt-0.5">
                {new Date(v.created_at).toLocaleString("zh-CN")}
              </p>
            </div>
            {v.version_number !== currentVersion && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleRollback(v.version_number)}
                disabled={rollingBack !== null}
                className="shrink-0 text-xs"
              >
                {rollingBack === v.version_number ? "回滚中..." : "回滚"}
              </Button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
