"use client"

import type { MediaJobProgressRef } from "@/components/assistant/extractChatArtifacts"

const SUBTYPE_LABELS: Record<string, string> = {
  immersive_classroom: "沉浸课堂",
  video: "讲解视频",
  classroom_video_export: "MP4 导出",
}

function labelFor(job: MediaJobProgressRef): string {
  if (job.subtype && SUBTYPE_LABELS[job.subtype]) return SUBTYPE_LABELS[job.subtype]
  return "多模态生成"
}

export function MediaJobProgressCard({ job }: { job: MediaJobProgressRef }) {
  const progress = Math.max(0, Math.min(100, job.progress || 0))

  return (
    <div className="glass-card rounded-3xl rounded-tl-md border border-amber-200/60 bg-gradient-to-br from-white via-amber-50/40 to-orange-50/30 p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-amber-700">{labelFor(job)}</p>
          <p className="mt-1 text-sm font-semibold text-on-surface">{job.message}</p>
        </div>
        <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[10px] font-bold text-amber-800">
          后台生成中
        </span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-amber-100">
        <div
          className="h-full rounded-full bg-gradient-to-r from-amber-500 to-orange-500 transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>
      <p className="mt-2 text-xs text-on-surface-variant">
        {job.stage || "processing"} · {progress}%
      </p>
    </div>
  )
}
