"use client"

import { cn } from "@/lib/utils"
import type { AssistantMode } from "@/types/agent"

interface ModeToggleProps {
  mode: AssistantMode
  onChange: (mode: AssistantMode) => void
}

export function ModeToggle({ mode, onChange }: ModeToggleProps) {
  return (
    <div className="inline-flex rounded-full border border-white/80 bg-white/60 p-1 shadow-sm">
      <button
        type="button"
        onClick={() => onChange("fast")}
        className={cn(
          "rounded-full px-4 py-1.5 text-xs font-bold transition-all",
          mode === "fast" ? "bg-primary text-on-primary shadow-sm" : "text-outline hover:text-primary",
        )}
      >
        快速回答
      </button>
      <button
        type="button"
        onClick={() => onChange("agent")}
        className={cn(
          "rounded-full px-4 py-1.5 text-xs font-bold transition-all",
          mode === "agent" ? "bg-primary text-on-primary shadow-sm" : "text-outline hover:text-primary",
        )}
      >
        智能体模式
      </button>
    </div>
  )
}
