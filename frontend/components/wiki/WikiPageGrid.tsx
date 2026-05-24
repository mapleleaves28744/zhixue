"use client"

import Link from "next/link"
import type { WikiPageListItem } from "@/types/wiki"

interface WikiPageGridProps {
  pages: WikiPageListItem[]
}

export function WikiPageGrid({ pages }: WikiPageGridProps) {
  if (pages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <span className="material-symbols-outlined text-6xl text-outline/30 mb-4">
          menu_book
        </span>
        <p className="font-headline-sm text-on-surface-variant mb-2">
          还没有 Wiki 页面
        </p>
        <p className="font-body-md text-on-surface-variant/60">
          从资料生成或手动创建第一个 Wiki 页面
        </p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {pages.map((page) => (
        <Link
          key={page.id}
          href={`/student/wiki/${page.id}`}
          className="glass-card p-5 flex flex-col gap-3 hover:bg-white/95 transition-all group"
        >
          <div className="flex items-start justify-between gap-2">
            <h3 className="font-headline-sm text-headline-sm text-on-surface line-clamp-2 group-hover:text-primary transition-colors">
              {page.title}
            </h3>
            <span className="shrink-0 px-2 py-0.5 rounded-md bg-primary/10 text-primary font-label-sm text-[10px]">
              v{page.current_version}
            </span>
          </div>
          {page.summary && (
            <p className="font-body-md text-body-md text-on-surface-variant line-clamp-3">
              {page.summary}
            </p>
          )}
          <div className="mt-auto flex items-center justify-between text-[12px] text-on-surface-variant font-medium pt-2 border-t border-outline-variant/20">
            <span className="flex items-center gap-1">
              <span className="material-symbols-outlined text-[14px]">update</span>
              {new Date(page.updated_at).toLocaleDateString("zh-CN")}
            </span>
            <span
              className={`px-2 py-0.5 rounded-md font-label-sm text-[10px] ${
                page.status === "active"
                  ? "bg-primary/10 text-primary"
                  : "bg-surface-container-high text-on-surface-variant"
              }`}
            >
              {page.status === "active" ? "活跃" : "已归档"}
            </span>
          </div>
        </Link>
      ))}
    </div>
  )
}
