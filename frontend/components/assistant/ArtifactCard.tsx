"use client"

import { useState } from "react"
import { MarkdownRenderer } from "@/components/markdown/MarkdownRenderer"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { MediaAssetPreview } from "@/components/assistant/MediaAssetPreview"

interface ArtifactCardProps {
  artifact: Record<string, unknown>
}

export function ArtifactCard({ artifact }: ArtifactCardProps) {
  const [open, setOpen] = useState(false)
  const type = String(artifact.type || artifact.artifact_type || "resource")
  const title = String(artifact.title || artifact.name || type)
  const assetId = artifact.asset_id ? String(artifact.asset_id) : null
  const mimeType = String(artifact.mime_type || "")

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex h-24 w-36 flex-col items-center justify-center rounded-2xl border border-white/80 bg-white/60 p-2 text-center shadow-sm transition hover:border-primary/40 hover:shadow-md"
      >
        <span className="material-symbols-outlined text-2xl text-primary">
          {type.includes("video")
            ? "movie"
            : type.includes("image")
              ? "image"
              : type.includes("audio") || mimeType.startsWith("audio/")
                ? "graphic_eq"
                : "description"}
        </span>
        <span className="mt-1 line-clamp-2 text-[11px] font-semibold text-on-surface">{title}</span>
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
          </DialogHeader>
          {assetId ? (
            <MediaPreview
              assetId={assetId}
              mimeType={String(artifact.mime_type || "")}
              subtype={artifact.subtype ? String(artifact.subtype) : undefined}
            />
          ) : artifact.content ? (
            <MarkdownRenderer content={String(artifact.content)} />
          ) : (
            <pre className="overflow-x-auto rounded-xl bg-muted p-4 text-xs">
              {JSON.stringify(artifact, null, 2)}
            </pre>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}

function MediaPreview({ assetId, mimeType, subtype }: { assetId: string; mimeType: string; subtype?: string }) {
  return (
    <MediaAssetPreview
      assetId={assetId}
      mimeType={mimeType}
      subtype={subtype}
    />
  )
}
