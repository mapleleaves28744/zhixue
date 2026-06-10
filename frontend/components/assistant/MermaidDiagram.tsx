"use client"

import { normalizeMermaidCode } from "@/lib/mermaid"
import { useEffect, useRef, useState } from "react"

type MermaidApi = {
  initialize: (config: Record<string, unknown>) => void
  render: (id: string, code: string) => Promise<{ svg: string }>
}

declare global {
  interface Window {
    mermaid?: MermaidApi
  }
}

function loadMermaid(): Promise<MermaidApi> {
  if (window.mermaid) {
    return Promise.resolve(window.mermaid)
  }
  return new Promise((resolve, reject) => {
    const existing = document.querySelector('script[data-zhixue-mermaid="1"]')
    if (existing) {
      existing.addEventListener("load", () => resolve(window.mermaid!))
      existing.addEventListener("error", reject)
      return
    }
    const script = document.createElement("script")
    script.src = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"
    script.async = true
    script.dataset.zhixueMermaid = "1"
    script.onload = () => resolve(window.mermaid!)
    script.onerror = () => reject(new Error("Mermaid 加载失败"))
    document.head.appendChild(script)
  })
}

interface MermaidDiagramProps {
  code: string
  title?: string
}

export function MermaidDiagram({ code, title }: MermaidDiagramProps) {
  const hostRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)
  const normalized = normalizeMermaidCode(code, title?.slice(0, 20) || "知识结构")

  useEffect(() => {
    let cancelled = false
    setError(null)

    loadMermaid()
      .then(async (mermaid) => {
        if (cancelled || !hostRef.current) return
        mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "loose" })
        const { svg } = await mermaid.render(`zhixue-mmd-${Date.now()}`, normalized)
        if (!cancelled && hostRef.current) {
          hostRef.current.innerHTML = svg
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError("思维导图渲染失败，请尝试重新生成。")
        }
      })

    return () => {
      cancelled = true
    }
  }, [normalized])

  return (
    <div className="overflow-hidden rounded-2xl border border-primary/15 bg-white shadow-sm">
      <div className="flex items-center gap-2 border-b border-primary/10 bg-primary/5 px-4 py-3 text-sm font-bold text-primary">
        <span className="material-symbols-outlined text-lg">account_tree</span>
        思维导图预览
      </div>
      {error ? (
        <p className="p-4 text-sm font-semibold text-error">{error}</p>
      ) : (
        <div ref={hostRef} className="flex min-h-[280px] items-center justify-center overflow-auto p-4" />
      )}
      <details className="border-t border-primary/10 bg-white/80 px-4 py-3">
        <summary className="cursor-pointer text-xs font-bold text-outline">查看 Mermaid 源码</summary>
        <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-xs leading-6 text-on-surface">
          {normalized}
        </pre>
      </details>
    </div>
  )
}
