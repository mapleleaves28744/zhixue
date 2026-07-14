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
  "image",
  "video",
  "animation",
  "interactive_courseware",
  "immersive_classroom",
  "code_project",
  "reading_pack",
]) {
  assert.match(resourceTypeHelpers, new RegExp(`value:\\s*"${type}"`))
}

for (const type of ["mindmap", "diagram", "image"]) {
  assert.match(resourceTypes, new RegExp(`\\|\\s*"${type}"`))
}

assert.doesNotMatch(resourceTypeHelpers, /value:\s*"mindmap"/)
assert.doesNotMatch(resourceTypeHelpers, /value:\s*"diagram"/)
assert.match(resourceTypeHelpers, /label:\s*"图片"/)

assert.match(sidePanel, /resourceType:\s*targetType/)
assert.match(sidePanel, /highlightResourceType/)
assert.match(sidePanel, /已放入「\$\{getResourceTypeLabel\(nextType\)\}」分类|后台生成中/)
assert.doesNotMatch(sidePanel, /focusResourceId/)
assert.match(assistant, /resourceTypeFromEvent/)
assert.match(assistant, /highlightResourceType=\{resourceRevealType\}/)

console.log("resource side panel category contract ok")
