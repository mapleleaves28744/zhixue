export function isMermaidContent(content: string): boolean {
  const trimmed = String(content || "").trim()
  return /^(mindmap|flowchart\s+(TD|LR|BT|RL)|sequenceDiagram|classDiagram|erDiagram)\b/.test(trimmed)
}

export function normalizeMermaidCode(content: string, rootLabel = "知识结构"): string {
  let text = String(content || "")
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/\r/g, "")
    .trim()

  if (!text) {
    return `mindmap\n  root((${rootLabel}))`
  }

  const fenced = text.match(/```mermaid\s*\n([\s\S]*?)```/i)
  if (fenced) {
    text = fenced[1].trim()
  }

  if (isMermaidContent(text) && text.includes("\n")) {
    const first = text.split("\n", 1)[0].trim()
    if (first === "mindmap" || first.startsWith("flowchart")) {
      return sanitizeMermaidLabels(text)
    }
  }

  const singleRoot = text.match(/^mindmap\s+root\(\((.+)\)\)\s*$/i)
  if (singleRoot) {
    const root = singleRoot[1].trim().slice(0, 40)
    return `mindmap\n  root((${root}))`
  }

  const lines = text.split("\n")
  if (lines[0] && /mindmap/i.test(lines[0])) {
    const rootMatch = lines[0].match(/root\(\((.+?)\)\)/i)
    const root = (rootMatch?.[1] || rootLabel).trim().slice(0, 40)
    const branches: string[] = []
    let currentSection: string | null = null

    for (const raw of lines.slice(1)) {
      const line = raw.trim()
      if (!line) continue
      const section = line.match(/^\*\*(.+?)\*\*$/)
      if (section) {
        currentSection = section[1].trim().slice(0, 20)
        branches.push(`    ${currentSection}`)
        continue
      }
      const cleaned = line.replace(/[*#:`"]/g, "").trim().slice(0, 32)
      if (!cleaned) continue
      branches.push(currentSection ? `      ${cleaned}` : `    ${cleaned}`)
    }

    if (branches.length) {
      return `mindmap\n  root((${root}))\n${branches.slice(0, 14).join("\n")}`
    }
    return `mindmap\n  root((${root}))\n    核心概念`
  }

  if (isMermaidContent(text)) {
    return sanitizeMermaidLabels(text)
  }

  return `mindmap\n  root((${rootLabel.slice(0, 40)}))\n    请重新生成`
}

function sanitizeMermaidLabels(code: string): string {
  return code
    .split("\n")
    .map((line) => line.replace(/<br\s*\/?>/gi, " ").replace(/[“”]/g, '"'))
    .join("\n")
    .trim()
}

export function getResourcePreviewMode(resource: {
  resource_type: string
  preview_mode?: string | null
  content: string
  media_asset_id?: string | null
  media_mime_type?: string | null
  media_asset_type?: string | null
}): "image" | "audio" | "video" | "mermaid" | "html" | "immersive_classroom" | "text" {
  if (
    (resource.resource_type === "mindmap" || resource.resource_type === "diagram") &&
    isMermaidContent(resource.content)
  ) {
    return "mermaid"
  }
  if (
    resource.preview_mode === "image" ||
    resource.preview_mode === "audio" ||
    resource.preview_mode === "video" ||
    resource.preview_mode === "mermaid" ||
    resource.preview_mode === "html" ||
    resource.preview_mode === "immersive_classroom"
  ) {
    return resource.preview_mode
  }
  const mime = resource.media_mime_type || ""
  if (resource.media_asset_id) {
    if (mime.startsWith("video/")) return "video"
    if (mime.startsWith("audio/")) return "audio"
    if (mime.startsWith("image/")) return "image"
    if (mime.startsWith("text/html") || resource.media_asset_type === "html") return "html"
    if (mime.includes("openmaic-classroom")) return "immersive_classroom"
  }
  if (
    resource.resource_type === "image" ||
    isMermaidContent(resource.content)
  ) {
    return resource.resource_type === "image" && resource.media_asset_id ? "image" : "mermaid"
  }
  if (resource.resource_type === "interactive_courseware") return "html"
  if (resource.resource_type === "immersive_classroom") return "immersive_classroom"
  return "text"
}
