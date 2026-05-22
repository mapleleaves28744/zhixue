"use client"

import { useState } from "react"

import { parseMaterial } from "@/services/materialService"
import type { Material } from "@/types/material"

interface MaterialListProps {
  loading: boolean
  materials: Material[]
  onParsed: () => void
}

const statusMeta: Record<string, { label: string; icon: string; className: string }> = {
  pending: {
    label: "待解析",
    icon: "schedule",
    className: "border-[#d7c3ae]/80 bg-white/55 text-[#857462]"
  },
  processing: {
    label: "解析中",
    icon: "progress_activity",
    className: "border-[#d7c3ae]/80 bg-[#ffddb5]/45 text-[#835400]"
  },
  success: {
    label: "解析成功",
    icon: "check_circle",
    className: "border-[#b8d9c2]/80 bg-[#e3f3e7]/70 text-[#2f6b3f]"
  },
  failed: {
    label: "解析失败",
    icon: "error",
    className: "border-[#ffdad6] bg-[#ffdad6]/50 text-[#93000a]"
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)}KB`
  }
  return `${(bytes / 1024 / 1024).toFixed(2)}MB`
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return "刚刚更新"
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date)
}

export function MaterialList({ loading, materials, onParsed }: MaterialListProps) {
  const [parsingId, setParsingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleParse(materialId: string) {
    setError(null)
    try {
      setParsingId(materialId)
      await parseMaterial(materialId)
      onParsed()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "资料解析失败")
      onParsed()
    } finally {
      setParsingId(null)
    }
  }

  return (
    <section className="rounded-[28px] border border-white/70 bg-white/50 p-6 shadow-[0_24px_70px_rgba(131,84,0,0.08)] backdrop-blur-3xl">
      <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#857462]">Material Library</p>
          <h2 className="mt-1 font-['Plus_Jakarta_Sans'] text-2xl font-bold text-[#1c1b1b]">课程资料列表</h2>
        </div>
        <span className="rounded-full border border-white/70 bg-white/55 px-4 py-2 text-sm font-bold text-[#524434]">
          {materials.length} 份资料
        </span>
      </div>

      {error ? (
        <div className="mb-4 rounded-2xl border border-[#ffdad6] bg-[#ffdad6]/45 px-4 py-3 text-sm font-semibold text-[#93000a]">
          {error}
        </div>
      ) : null}

      {loading ? (
        <div className="grid gap-4">
          {Array.from({ length: 3 }).map((_, index) => (
            <div className="h-24 animate-pulse rounded-[24px] bg-white/50" key={index} />
          ))}
        </div>
      ) : materials.length > 0 ? (
        <div className="grid gap-4">
          {materials.map((material) => {
            const meta = statusMeta[material.parse_status] ?? statusMeta.pending
            const canParse = material.parse_status !== "processing"
            return (
              <article
                className="rounded-[24px] border border-white/70 bg-white/45 p-5 transition hover:bg-white/70"
                key={material.id}
              >
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="mb-3 flex flex-wrap items-center gap-2">
                      <span className="rounded-full border border-[#835400]/10 bg-[#ffddb5]/35 px-3 py-1 text-xs font-bold uppercase text-[#835400]">
                        {material.file_type}
                      </span>
                      <span className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-bold ${meta.className}`}>
                        <span className="material-symbols-outlined text-base">{meta.icon}</span>
                        {meta.label}
                      </span>
                    </div>
                    <h3 className="truncate text-lg font-bold text-[#1c1b1b]">{material.file_name}</h3>
                    <p className="mt-2 text-sm text-[#857462]">
                      {formatSize(material.file_size)} · 上传于 {formatDate(material.created_at)}
                    </p>
                    {material.parse_error ? (
                      <p className="mt-2 text-sm font-semibold text-[#93000a]">{material.parse_error}</p>
                    ) : null}
                  </div>
                  <button
                    className="inline-flex items-center justify-center gap-2 rounded-full bg-[#835400] px-5 py-3 text-sm font-bold text-white shadow-[0_10px_24px_rgba(131,84,0,0.16)] transition hover:bg-[#674100] disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={!canParse || parsingId === material.id}
                    onClick={() => void handleParse(material.id)}
                    type="button"
                  >
                    <span className="material-symbols-outlined text-lg">
                      {parsingId === material.id ? "hourglass_top" : "text_snippet"}
                    </span>
                    {parsingId === material.id ? "解析中" : "解析文本"}
                  </button>
                </div>
              </article>
            )
          })}
        </div>
      ) : (
        <div className="rounded-[24px] border border-dashed border-[#d7c3ae] bg-white/35 p-8 text-center">
          <span className="material-symbols-outlined text-4xl text-[#835400]">folder_open</span>
          <p className="mt-3 text-lg font-bold text-[#524434]">暂无课程资料</p>
          <p className="mt-2 text-sm leading-7 text-[#857462]">上传讲义、课件或笔记后，解析状态会显示在这里。</p>
        </div>
      )}
    </section>
  )
}
