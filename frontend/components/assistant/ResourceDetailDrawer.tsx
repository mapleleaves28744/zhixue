"use client"

import { ResourcePreviewBody } from "@/components/assistant/ResourcePreviewBody"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { getResourceTypeLabel } from "@/lib/resourceTypes"
import type { GeneratedResource } from "@/types/resource"

interface ResourceDetailDrawerProps {
  resource: GeneratedResource | null
  open: boolean
  onOpenChange: (open: boolean) => void
  mediaJobId?: string | null
  onResourceUpdated?: (resource: GeneratedResource) => void
}

export function ResourceDetailDrawer({
  resource,
  open,
  onOpenChange,
  mediaJobId = null,
  onResourceUpdated,
}: ResourceDetailDrawerProps) {
  if (!resource) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{resource.title}</DialogTitle>
          <p className="text-xs text-outline">
            {getResourceTypeLabel(resource.resource_type)} ·{" "}
            {new Date(resource.created_at).toLocaleString()}
          </p>
        </DialogHeader>

        <ResourcePreviewBody
          resource={resource}
          showPersonalizedReason
          collapseScript={resource.resource_type === "explanation"}
          mediaJobId={mediaJobId}
          onResourceUpdated={onResourceUpdated}
        />
      </DialogContent>
    </Dialog>
  )
}
