"use client"

import { cn } from "@/lib/utils"
import { TOOL_OPTIONS } from "@/types/agent"

interface ToolSelectorProps {
  selected: string[]
  onChange: (tools: string[]) => void
  disabled?: boolean
}

export function ToolSelector({ selected, onChange, disabled }: ToolSelectorProps) {
  const toggle = (id: string) => {
    if (disabled) return
    onChange(selected.includes(id) ? selected.filter((t) => t !== id) : [...selected, id])
  }

  return (
    <div className="flex flex-wrap gap-2">
      {TOOL_OPTIONS.map((tool) => {
        const active = selected.includes(tool.id)
        return (
          <button
            key={tool.id}
            type="button"
            disabled={disabled}
            onClick={() => toggle(tool.id)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs font-semibold transition-all",
              active
                ? "border-primary/40 bg-primary/10 text-primary"
                : "border-white/80 bg-white/50 text-outline hover:border-primary/30 hover:text-primary",
              disabled && "cursor-not-allowed opacity-50",
            )}
          >
            {tool.label}
          </button>
        )
      })}
    </div>
  )
}
