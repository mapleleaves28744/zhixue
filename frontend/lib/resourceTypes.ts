import type { ResourceType } from "@/types/resource"

export const RESOURCE_CATEGORY_OPTIONS: { value: ResourceType; label: string }[] = [
  { value: "explanation", label: "讲解" },
  { value: "summary", label: "总结" },
  { value: "example", label: "例题" },
  { value: "flashcard", label: "复习卡" },
  { value: "review", label: "错题解析" },
  { value: "image", label: "图片" },
  { value: "video", label: "讲解视频" },
  { value: "animation", label: "动画演示" },
  { value: "interactive_courseware", label: "互动课件" },
  { value: "immersive_classroom", label: "沉浸课堂" },
  { value: "code_project", label: "代码实操" },
  { value: "reading_pack", label: "拓展阅读" },
]

export const RESOURCE_TYPE_LABELS: Record<ResourceType, string> = {
  explanation: "讲解",
  summary: "总结",
  example: "例题",
  flashcard: "复习卡",
  review: "错题解析",
  mindmap: "图片",
  diagram: "图片",
  image: "图片",
  video: "讲解视频",
  animation: "动画演示",
  interactive_courseware: "互动课件",
  immersive_classroom: "沉浸课堂",
  code_project: "代码实操",
  reading_pack: "拓展阅读",
}

const RESOURCE_TYPE_VALUES = new Set<ResourceType>([
  ...RESOURCE_CATEGORY_OPTIONS.map((item) => item.value),
  "mindmap",
  "diagram",
])

const RESOURCE_TYPE_ALIASES: Record<string, ResourceType> = {
  courseware: "interactive_courseware",
  interactive_classroom: "interactive_courseware",
  immersive_classroom: "immersive_classroom",
  narrated_classroom_video: "video",
  storyboard: "video",
  media_video: "video",
  media_image: "image",
  mermaid: "image",
  mindmap: "image",
  diagram: "image",
  思维导图: "image",
  图解: "image",
  教学插图: "image",
}

export function normalizeResourceType(value: unknown): ResourceType | null {
  if (typeof value !== "string") return null
  const raw = value.trim()
  if (!raw) return null
  if (RESOURCE_TYPE_VALUES.has(raw as ResourceType)) {
    if (raw === "mindmap" || raw === "diagram") return "image"
    return raw as ResourceType
  }
  const aliased = RESOURCE_TYPE_ALIASES[raw]
  if (aliased) return aliased
  return null
}

export function getResourceTypeLabel(value: unknown, fallback = "资源"): string {
  const normalized = normalizeResourceType(value)
  if (!normalized) return typeof value === "string" && value.trim() ? value : fallback
  return RESOURCE_TYPE_LABELS[normalized]
}
