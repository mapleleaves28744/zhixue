"use client"

import { buildApiUrl } from "@/lib/api"
import { getToken } from "@/lib/auth"
import type { ChatMediaArtifactRef } from "@/components/assistant/extractChatArtifacts"

export function ImmersiveClassroomCard({ artifact }: { artifact: ChatMediaArtifactRef }) {
  const token = getToken()
  const launchUrl = buildApiUrl(`/api/v1/media-assets/${artifact.id}/launch`)
  const href = token ? `${launchUrl}?access_token=${encodeURIComponent(token)}` : launchUrl

  return (
    <div className="overflow-hidden rounded-3xl border border-indigo-200/70 bg-gradient-to-br from-white via-indigo-50/70 to-cyan-50/70 p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-indigo-500">OpenMAIC 沉浸课堂</p>
          <h3 className="mt-2 text-lg font-bold text-slate-900">{artifact.title || "个性化沉浸课堂"}</h3>
        </div>
        <span className="material-symbols-outlined rounded-2xl bg-indigo-600 p-2 text-white">co_present</span>
      </div>

      <div className="mt-4 flex flex-wrap gap-2 text-xs font-semibold text-slate-600">
        {artifact.scenesCount != null ? (
          <span className="rounded-full bg-white/80 px-3 py-1">{artifact.scenesCount} 个课堂场景</span>
        ) : null}
        {artifact.citationCount != null ? (
          <span className="rounded-full bg-white/80 px-3 py-1">{artifact.citationCount} 条课程依据</span>
        ) : null}
        <span className="rounded-full bg-emerald-50 px-3 py-1 text-emerald-700">独立来源安全播放</span>
      </div>

      {artifact.personalizedReason ? (
        <p className="mt-4 text-sm leading-6 text-slate-600">个性化依据：{artifact.personalizedReason}</p>
      ) : null}

      <a
        href={href}
        target="_blank"
        rel="noreferrer"
        className="mt-5 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-500 px-4 py-2 text-sm font-bold text-white shadow-sm transition hover:shadow-md"
      >
        <span className="material-symbols-outlined text-lg">play_circle</span>
        进入沉浸课堂
      </a>
    </div>
  )
}
