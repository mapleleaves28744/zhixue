"use client"

import type { LearningPathDetail } from "@/types/learningPath"

const STATUS_LABELS: Record<string, string> = {
  pending: "待学习",
  doing: "进行中",
  completed: "已完成",
  skipped: "已跳过",
}

export function InlineLearningPathPreview({ path }: { path: LearningPathDetail }) {
  return (
    <div className="space-y-3">
      {path.reason ? (
        <p className="text-sm leading-6 text-on-surface-variant">{path.reason}</p>
      ) : null}
      <ol className="space-y-2">
        {path.items
          .slice()
          .sort((a, b) => a.order_index - b.order_index)
          .map((item, index) => (
            <li
              key={item.id}
              className="flex gap-3 rounded-2xl border border-white/80 bg-white/60 px-4 py-3 text-sm"
            >
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                {index + 1}
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-on-surface">{item.title}</p>
                {item.reason ? (
                  <p className="mt-1 text-xs leading-5 text-outline">{item.reason}</p>
                ) : null}
                <p className="mt-1 text-xs text-outline">
                  {STATUS_LABELS[item.status] || item.status}
                  {item.estimated_minutes ? ` · 约 ${item.estimated_minutes} 分钟` : ""}
                </p>
              </div>
            </li>
          ))}
      </ol>
    </div>
  )
}
