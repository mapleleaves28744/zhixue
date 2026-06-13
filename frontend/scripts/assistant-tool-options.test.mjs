import assert from "node:assert/strict"
import fs from "node:fs"
import path from "node:path"

const source = fs.readFileSync(
  path.resolve(import.meta.dirname, "..", "types", "agent.ts"),
  "utf8",
)

assert.match(source, /\{\s*id:\s*"generate_lesson_video",\s*label:\s*"快速讲解视频"\s*\}/)
assert.match(source, /\{\s*id:\s*"generate_immersive_classroom",\s*label:\s*"沉浸课堂"\s*\}/)

console.log("assistant tool option assertions passed")
