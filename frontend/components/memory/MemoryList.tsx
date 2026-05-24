"use client"

import { Button } from "@/components/ui/button"
import type { StudentMemory } from "@/types/memory"

interface MemoryListProps {
  memories: StudentMemory[]
  onDelete: (id: string) => void
  onReflect: () => void
  reflecting: boolean
}

const MEMORY_TYPE_ICONS: Record<string, string> = {
  insight: "lightbulb",
  mistake_pattern: "bug_report",
  preference: "psychology_alt",
}

const MEMORY_TYPE_LABELS: Record<string, string> = {
  insight: "洞察",
  mistake_pattern: "错误模式",
  preference: "偏好",
}

export function MemoryList({ memories, onDelete, onReflect, reflecting }: MemoryListProps) {
  return (
    <div className="glass-card rounded-xl p-8">
      <div className="flex justify-between items-center mb-6">
        <h3 className="font-headline-md text-headline-md flex items-center">
          <span className="material-symbols-outlined mr-2 text-tertiary">memory</span>
          长期记忆
        </h3>
        <Button
          variant="outline"
          size="sm"
          onClick={onReflect}
          disabled={reflecting}
        >
          <span className="material-symbols-outlined text-[18px] mr-1">
            {reflecting ? "hourglass_top" : "auto_awesome"}
          </span>
          {reflecting ? "反思中..." : "反思生成记忆"}
        </Button>
      </div>

      {memories.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-on-surface-variant">
          <span className="material-symbols-outlined text-4xl mb-3 opacity-40">memory</span>
          <p className="text-body-md">暂无长期记忆</p>
          <p className="text-label-md mt-1">点击"反思生成记忆"开始</p>
        </div>
      ) : (
        <div className="space-y-3 max-h-[500px] overflow-y-auto pr-2">
          {memories.map((memory) => (
            <div
              key={memory.id}
              className="group p-4 bg-surface-container-low rounded-xl hover:bg-white hover:shadow-sm transition-all flex items-center justify-between border border-transparent hover:border-outline-variant/30"
            >
              <div className="flex items-center space-x-4 flex-1 min-w-0">
                <div className="w-10 h-10 rounded-lg bg-tertiary-fixed text-on-tertiary-fixed-variant flex items-center justify-center shrink-0">
                  <span className="material-symbols-outlined">
                    {MEMORY_TYPE_ICONS[memory.memory_type] || "bookmark"}
                  </span>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-label-sm px-2 py-0.5 rounded-full bg-primary-fixed text-on-primary-fixed-variant">
                      {MEMORY_TYPE_LABELS[memory.memory_type] || memory.memory_type}
                    </span>
                    <span className="text-label-sm text-on-surface-variant">
                      置信度 {Math.round(memory.confidence * 100)}%
                    </span>
                  </div>
                  <p className="text-body-md text-on-surface truncate">{memory.content}</p>
                  {memory.evidence.length > 0 && (
                    <p className="text-label-sm text-on-surface-variant mt-1">
                      来源: {memory.evidence.slice(0, 2).join(", ")}
                      {memory.evidence.length > 2 ? ` +${memory.evidence.length - 2}` : ""}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity ml-4">
                <button
                  onClick={() => onDelete(memory.id)}
                  className="p-2 text-error hover:bg-error-container rounded-lg"
                  title="删除"
                >
                  <span className="material-symbols-outlined text-sm">delete</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
