import assert from "node:assert/strict"
import fs from "node:fs"

const resourceTypes = fs.readFileSync(new URL("../types/resource.ts", import.meta.url), "utf8")
const resourceTypeHelpers = fs.readFileSync(new URL("../lib/resourceTypes.ts", import.meta.url), "utf8")
const sidePanel = fs.readFileSync(new URL("../components/assistant/ResourceSidePanel.tsx", import.meta.url), "utf8")
const assistant = fs.readFileSync(new URL("../components/assistant/AssistantPageClient.tsx", import.meta.url), "utf8")

for (const type of [
  "explanation",
  "summary",
  "example",
  "flashcard",
  "review",
  "mindmap",
  "diagram",
  "image",
  "video",
  "animation",
  "interactive_courseware",
  "immersive_classroom",
  "code_project",
  "reading_pack",
]) {
  assert.match(resourceTypes, new RegExp(`\\|\\s*"${type}"`))
  assert.match(resourceTypeHelpers, new RegExp(`value:\\s*"${type}"`))
}

assert.match(sidePanel, /resourceType:\s*targetType/)
assert.match(sidePanel, /highlightResourceType/)
assert.match(sidePanel, /已放入「\$\{getResourceTypeLabel\(nextType\)\}」分类/)
assert.match(assistant, /resourceTypeFromEvent/)
assert.match(assistant, /highlightResourceType=\{resourceRevealType\}/)

console.log("resource side panel category contract ok")
