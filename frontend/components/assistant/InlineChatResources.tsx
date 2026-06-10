"use client"

import { useEffect, useMemo, useState } from "react"
import {
  ResourcePreviewBody,
  shouldInlineResource,
} from "@/components/assistant/ResourcePreviewBody"
import { getResource } from "@/services/resourceService"
import type { ChatArtifactRef } from "@/components/assistant/extractChatArtifacts"
import type { GeneratedResource } from "@/types/resource"

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

function resourceIcon(resourceType: string): string {
  if (resourceType === "mindmap") return "account_tree"
  if (resourceType === "diagram") return "schema"
  if (resourceType === "explanation") return "volume_up"
  return "image"
}

interface InlineChatResourcesProps {
  refs: ChatArtifactRef[]
}

export function InlineChatResources({ refs }: InlineChatResourcesProps) {
  const refKey = useMemo(() => refs.map((r) => r.id).join(","), [refs])
  const [resources, setResources] = useState<GeneratedResource[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!refs.length) {
      setResources([])
      return
    }
    let cancelled = false
    setLoading(true)
    Promise.all(refs.map((ref) => getResource(ref.id).catch(() => null)))
      .then((items) => {
        if (cancelled) return
        setResources(items.filter(Boolean) as GeneratedResource[])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [refKey, refs])

  if (!refs.length) return null

  const inlineResources = resources.filter(shouldInlineResource)
  if (!loading && !inlineResources.length) return null

  return (
    <div className="flex w-full flex-col gap-3">
      {loading && !inlineResources.length ? (
        <div className="glass-card rounded-3xl rounded-tl-md px-4 py-3 text-xs text-outline">
          正在加载生成内容…
        </div>
      ) : null}
      {inlineResources.map((resource) => {
        const typeLabel = TYPE_LABELS[resource.resource_type] || resource.resource_type
        return (
          <div key={resource.id} className="glass-card rounded-3xl rounded-tl-md p-4 shadow-sm">
            <p className="mb-3 flex flex-wrap items-center gap-2 text-sm font-bold text-primary">
              <span className="material-symbols-outlined text-lg">{resourceIcon(resource.resource_type)}</span>
              <span>{resource.title}</span>
              <span className="text-xs font-normal text-outline">{typeLabel}</span>
            </p>
            <ResourcePreviewBody
              resource={resource}
              collapseScript={resource.resource_type === "explanation"}
            />
          </div>
        )
      })}
    </div>
  )
}
