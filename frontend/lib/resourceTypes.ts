import type { ResourceType } from "@/types/resource"

export const RESOURCE_CATEGORY_OPTIONS: { value: ResourceType; label: string }[] = [
  { value: "explanation", label: "讲解" },
  { value: "summary", label: "总结" },
  { value: "example", label: "例题" },
  { value: "flashcard", label: "复习卡" },
  { value: "review", label: "错题解析" },
  { value: "mindmap", label: "思维导图" },
  { value: "diagram", label: "图解" },
  { value: "image", label: "教学插图" },
  { value: "video", label: "讲解视频" },
  { value: "animation", label: "动画演示" },
  { value: "interactive_courseware", label: "互动课件" },
  { value: "immersive_classroom", label: "沉浸课堂" },
  { value: "code_project", label: "代码实操" },
  { value: "reading_pack", label: "拓展阅读" },
]

export const RESOURCE_TYPE_LABELS: Record<ResourceType, string> = Object.fromEntries(
  RESOURCE_CATEGORY_OPTIONS.map((item) => [item.value, item.label]),
) as Record<ResourceType, string>

const RESOURCE_TYPE_VALUES = new Set<ResourceType>(RESOURCE_CATEGORY_OPTIONS.map((item) => item.value))

const RESOURCE_TYPE_ALIASES: Record<string, ResourceType> = {
  courseware: "interactive_courseware",
  interactive_classroom: "interactive_courseware",
  immersive_classroom: "immersive_classroom",
  narrated_classroom_video: "video",
  storyboard: "video",
  media_video: "video",
  media_image: "image",
  mermaid: "diagram",
}

export function normalizeResourceType(value: unknown): ResourceType | null {
  if (typeof value !== "string") return null
  const raw = value.trim()
  if (!raw) return null
  if (RESOURCE_TYPE_VALUES.has(raw as ResourceType)) return raw as ResourceType
  return RESOURCE_TYPE_ALIASES[raw] ?? null
}

export function getResourceTypeLabel(value: unknown, fallback = "资源"): string {
  const normalized = normalizeResourceType(value)
  if (!normalized) return typeof value === "string" && value.trim() ? value : fallback
  return RESOURCE_TYPE_LABELS[normalized]
}
