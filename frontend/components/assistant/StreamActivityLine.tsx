"use client"

import { cn } from "@/lib/utils"

interface StreamActivityLineProps {
  icon?: string
  label: string
  preview?: string
  streaming?: boolean
  error?: string | null
  onClick?: () => void
  className?: string
}

export function StreamActivityLine({
  icon = "auto_awesome",
  label,
  preview,
  streaming = false,
  error,
  onClick,
  className,
}: StreamActivityLineProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group flex w-full max-w-full items-start gap-2 rounded-2xl border border-white/70 bg-white/55 px-3 py-2 text-left shadow-sm transition hover:border-primary/30 hover:bg-white/80",
        className,
      )}
    >
      <span
        className={cn(
          "material-symbols-outlined mt-0.5 shrink-0 text-[18px] text-outline group-hover:text-primary",
          streaming && "animate-pulse text-primary",
        )}
      >
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold text-on-surface">{label}</span>
        {preview ? (
          <span className="mt-0.5 block truncate text-xs text-on-surface-variant">{preview}</span>
        ) : null}
        {error ? <span className="mt-0.5 block truncate text-xs text-destructive">{error}</span> : null}
      </span>
      <span className="material-symbols-outlined shrink-0 text-[18px] text-outline opacity-0 transition group-hover:opacity-100">
        open_in_full
      </span>
    </button>
  )
}
