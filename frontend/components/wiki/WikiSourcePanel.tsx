"use client"

import type { WikiSource } from "@/types/wiki"

interface WikiSourcePanelProps {
  sources: WikiSource[]
}

const sourceTypeLabels: Record<string, { label: string; icon: string; color: string }> = {
  material: { label: "课程资料", icon: "description", color: "bg-primary/10 text-primary" },
  chunk: { label: "文档切片", icon: "data_object", color: "bg-tertiary/10 text-tertiary" },
  knowledge_point: { label: "知识点", icon: "psychology", color: "bg-secondary/10 text-secondary" },
  note: { label: "学生笔记", icon: "edit_note", color: "bg-primary-container/30 text-on-primary-container" },
}

export function WikiSourcePanel({ sources }: WikiSourcePanelProps) {
  if (sources.length === 0) {
    return (
      <div className="text-center py-8 text-on-surface-variant/60">
        <span className="material-symbols-outlined text-3xl mb-2 block">link_off</span>
        <p className="font-body-md text-sm">暂无来源信息</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <h4 className="font-label-md text-label-md text-on-surface flex items-center gap-2">
        <span className="material-symbols-outlined text-[18px] text-primary">link</span>
        来源追溯
      </h4>
      {sources.map((source) => {
        const meta = sourceTypeLabels[source.source_type] || {
          label: source.source_type,
          icon: "bookmark",
          color: "bg-surface-container text-on-surface-variant",
        }
        return (
          <div
            key={source.id}
            className="glass-card p-3 flex flex-col gap-2"
          >
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[16px] text-primary">
                {meta.icon}
              </span>
              <span className={`px-2 py-0.5 rounded-md font-label-sm text-[10px] ${meta.color}`}>
                {meta.label}
              </span>
              {source.source_title && (
                <span className="font-body-md text-sm text-on-surface truncate">
                  {source.source_title}
                </span>
              )}
            </div>
            {source.quote_text && (
              <p className="font-body-md text-xs text-on-surface-variant line-clamp-3 border-l-2 border-outline-variant/30 pl-2">
                {source.quote_text}
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}
