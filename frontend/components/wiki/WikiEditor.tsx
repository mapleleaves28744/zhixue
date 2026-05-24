"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"

interface WikiEditorProps {
  initialTitle: string
  initialContent: string
  initialSummary?: string
  onSave: (data: {
    title: string
    content: string
    summary: string
    changeMessage: string
  }) => Promise<void>
  onCancel: () => void
}

export function WikiEditor({
  initialTitle,
  initialContent,
  initialSummary = "",
  onSave,
  onCancel,
}: WikiEditorProps) {
  const [title, setTitle] = useState(initialTitle)
  const [content, setContent] = useState(initialContent)
  const [summary, setSummary] = useState(initialSummary)
  const [changeMessage, setChangeMessage] = useState("")
  const [saving, setSaving] = useState(false)
  const [preview, setPreview] = useState(false)

  const handleSave = async () => {
    if (!title.trim() || !content.trim()) return
    try {
      setSaving(true)
      await onSave({ title, content, summary, changeMessage })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Header */}
      <div className="flex items-center justify-between">
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="页面标题"
          className="font-headline-md text-headline-md text-on-surface bg-transparent border-none outline-none flex-1 placeholder-on-surface-variant/40"
        />
        <div className="flex gap-2">
          <Button variant="ghost" onClick={onCancel}>
            取消
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving || !title.trim() || !content.trim()}
          >
            {saving ? "保存中..." : "保存"}
          </Button>
        </div>
      </div>

      {/* Summary */}
      <input
        type="text"
        value={summary}
        onChange={(e) => setSummary(e.target.value)}
        placeholder="页面摘要（可选）"
        className="font-body-md text-body-md text-on-surface-variant bg-transparent border-b border-outline-variant/30 outline-none pb-2 placeholder-on-surface-variant/40"
      />

      {/* Change message */}
      <input
        type="text"
        value={changeMessage}
        onChange={(e) => setChangeMessage(e.target.value)}
        placeholder="变更说明（可选，如：修正了定义部分）"
        className="font-body-md text-sm text-on-surface-variant bg-transparent border-b border-outline-variant/30 outline-none pb-2 placeholder-on-surface-variant/40"
      />

      {/* Editor / Preview toggle */}
      <div className="flex gap-2">
        <button
          onClick={() => setPreview(false)}
          className={`px-3 py-1.5 rounded-lg font-label-md text-sm transition-all ${
            !preview
              ? "bg-primary text-on-primary"
              : "text-on-surface-variant hover:bg-surface-container"
          }`}
        >
          编辑
        </button>
        <button
          onClick={() => setPreview(true)}
          className={`px-3 py-1.5 rounded-lg font-label-md text-sm transition-all ${
            preview
              ? "bg-primary text-on-primary"
              : "text-on-surface-variant hover:bg-surface-container"
          }`}
        >
          预览
        </button>
      </div>

      {/* Content area */}
      {preview ? (
        <div className="flex-1 min-h-[400px] glass-card p-6 overflow-y-auto">
          <div className="font-body-md text-body-md text-on-surface whitespace-pre-wrap leading-relaxed">
            {content}
          </div>
        </div>
      ) : (
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="输入 Markdown 内容..."
          className="flex-1 min-h-[400px] glass-card p-6 font-mono text-sm text-on-surface bg-white/60 border border-white/80 rounded-2xl resize-none outline-none focus:border-primary/40 focus:ring-2 focus:ring-primary/10 transition-all"
        />
      )}
    </div>
  )
}
