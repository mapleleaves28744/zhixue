import assert from "node:assert/strict"
import fs from "node:fs"
import path from "node:path"

const root = path.resolve(import.meta.dirname, "..")
const mermaidSource = fs.readFileSync(path.join(root, "lib", "mermaid.ts"), "utf8")
const previewSource = fs.readFileSync(
  path.join(root, "components", "assistant", "ResourcePreviewBody.tsx"),
  "utf8",
)
const resourceTypesSource = fs.readFileSync(path.join(root, "types", "resource.ts"), "utf8")
const resourceTypeHelpers = fs.readFileSync(path.join(root, "lib", "resourceTypes.ts"), "utf8")

assert.match(mermaidSource, /preview_mode === "video"/)
assert.match(mermaidSource, /mime\.startsWith\("video\/"\)/)
assert.match(previewSource, /previewMode === "video"/)
assert.match(resourceTypesSource, /\|\s*"video"/)
assert.match(resourceTypeHelpers, /value:\s*"video", label:\s*"讲解视频"/)

console.log("resource video preview assertions passed")
