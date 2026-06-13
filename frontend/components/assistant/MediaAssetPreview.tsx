"use client"

import { useMemo, useState } from "react"
import { buildApiUrl } from "@/lib/api"
import { getToken } from "@/lib/auth"

interface MediaAssetPreviewProps {
  assetId: string
  mimeType?: string | null
  title?: string
  subtype?: string | null
  /** 对话流内嵌 HTML 课件：默认不自动加载 iframe，避免进入会话时批量请求 */
  lazyHtmlPreview?: boolean
}

function buildAssetSrc(assetId: string): string {
  const url = buildApiUrl(`/api/v1/media-assets/${assetId}/file`)
  const token = getToken()
  return token ? `${url}?access_token=${encodeURIComponent(token)}` : url
}

function resolvePreviewKind(mimeType: string | null | undefined, subtype?: string | null) {
  const mime = (mimeType || "").toLowerCase()
  if (mime.startsWith("video/")) return "video" as const
  if (mime.startsWith("audio/")) return "audio" as const
  if (mime.startsWith("image/")) return "image" as const
  if (mime.startsWith("text/html") || subtype === "courseware" || subtype === "storyboard") {
    return "html" as const
  }
  return "unknown" as const
}

export function MediaAssetPreview({
  assetId,
  mimeType,
  title,
  subtype,
  lazyHtmlPreview = false,
}: MediaAssetPreviewProps) {
  const src = useMemo(() => buildAssetSrc(assetId), [assetId])
  const previewKind = resolvePreviewKind(mimeType, subtype)
  const [htmlExpanded, setHtmlExpanded] = useState(!lazyHtmlPreview)

  if (previewKind === "video") {
    return <video controls className="max-h-[60vh] w-full rounded-xl" src={src} />
  }
  if (previewKind === "audio") {
    return <audio controls className="w-full max-w-lg" src={src} />
  }
  if (previewKind === "image") {
    return (
      <img
        alt={title || "教学插图"}
        className="max-h-[60vh] w-full rounded-xl object-contain"
        src={src}
      />
    )
  }
  if (previewKind === "html") {
    if (!htmlExpanded) {
      return (
        <div className="rounded-2xl border border-primary/15 bg-primary/5 p-4">
          <p className="text-sm text-on-surface-variant">
            互动课件已生成。点击下方按钮预览，不会在打开对话时自动下载。
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setHtmlExpanded(true)}
              className="inline-flex items-center gap-1 rounded-xl bg-primary px-4 py-2 text-sm font-bold text-on-primary"
            >
              <span className="material-symbols-outlined text-base">slideshow</span>
              在此预览课件
            </button>
            <a
              href={src}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 rounded-xl border border-primary/30 bg-white/80 px-4 py-2 text-sm font-semibold text-primary"
            >
              <span className="material-symbols-outlined text-base">open_in_new</span>
              新窗口打开
            </a>
          </div>
        </div>
      )
    }
    return (
      <iframe
        title={title || "互动课件"}
        src={src}
        className="h-[480px] w-full rounded-xl border border-border"
      />
    )
  }

  return (
    <div className="rounded-2xl border border-dashed border-primary/20 bg-white/50 p-4 text-sm text-outline">
      暂不支持内联预览该媒体类型，请在新窗口打开。
      <a href={src} target="_blank" rel="noreferrer" className="ml-2 font-semibold text-primary">
        打开文件
      </a>
    </div>
  )
}
