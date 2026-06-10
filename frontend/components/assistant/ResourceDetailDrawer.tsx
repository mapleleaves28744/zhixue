"use client"

import { ResourcePreviewBody } from "@/components/assistant/ResourcePreviewBody"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import type { GeneratedResource } from "@/types/resource"

interface ResourceDetailDrawerProps {
  resource: GeneratedResource | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

const TYPE_LABELS: Record<string, string> = {
  explanation: "讲解",
  summary: "总结",
  example: "例题",
  flashcard: "复习卡",
  review: "错题解析",
  mindmap: "思维导图",
  diagram: "图解",
  image: "教学插图",
}

export function ResourceDetailDrawer({ resource, open, onOpenChange }: ResourceDetailDrawerProps) {
  if (!resource) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{resource.title}</DialogTitle>
          <p className="text-xs text-outline">
            {TYPE_LABELS[resource.resource_type] || resource.resource_type} ·{" "}
            {new Date(resource.created_at).toLocaleString()}
          </p>
        </DialogHeader>

        <ResourcePreviewBody
          resource={resource}
          showPersonalizedReason
          collapseScript={resource.resource_type === "explanation"}
        />
      </DialogContent>
    </Dialog>
  )
}
