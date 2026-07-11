"use client"

import { useEffect } from "react"
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog"
import {
  ResourceSidePanel,
  type ResourceSidePanelProps,
} from "@/components/assistant/ResourceSidePanel"

interface ResourcePanelDialogProps extends ResourceSidePanelProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function ResourcePanelDialog({
  open,
  onOpenChange,
  ...resourceProps
}: ResourcePanelDialogProps) {
  useEffect(() => {
    if (!open) return
    const desktop = window.matchMedia("(min-width: 1280px)")
    const closeOnDesktop = (event: MediaQueryListEvent | MediaQueryList) => {
      if (event.matches) onOpenChange(false)
    }
    closeOnDesktop(desktop)
    desktop.addEventListener("change", closeOnDesktop)
    return () => desktop.removeEventListener("change", closeOnDesktop)
  }, [onOpenChange, open])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-xl:bottom-0 max-xl:left-0 max-xl:top-auto max-xl:w-full max-xl:max-w-none max-xl:translate-x-0 max-xl:translate-y-0 max-xl:rounded-b-none md:bottom-4 md:left-auto md:right-0 md:top-4 md:w-[420px] md:translate-x-0 md:translate-y-0 md:p-2"
      >
        <DialogTitle className="sr-only">个性化学习资源</DialogTitle>
        <DialogDescription className="sr-only">
          查看或生成与当前课程相关的个性化学习资源。
        </DialogDescription>
        <ResourceSidePanel {...resourceProps} className="h-[min(76dvh,720px)] md:h-full" />
      </DialogContent>
    </Dialog>
  )
}
