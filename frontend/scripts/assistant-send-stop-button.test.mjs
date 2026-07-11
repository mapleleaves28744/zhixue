import assert from "node:assert/strict"
import fs from "node:fs"
import path from "node:path"

const assistantSource = fs.readFileSync(
  path.resolve(import.meta.dirname, "..", "components", "assistant", "AssistantPageClient.tsx"),
  "utf8",
)
const replyBlocksSource = fs.readFileSync(
  path.resolve(import.meta.dirname, "..", "components", "assistant", "ReplyBlocks.tsx"),
  "utf8",
)
const tutorStreamSource = fs.readFileSync(
  path.resolve(import.meta.dirname, "..", "hooks", "useTutorStream.ts"),
  "utf8",
)

assert.match(assistantSource, /const hasActiveStream = messages\.some/)
assert.match(assistantSource, /aria-label="停止生成"/)
assert.match(assistantSource, /stopVisibleStreams\(true\)/)
assert.match(assistantSource, /rounded-full/)
assert.match(assistantSource, /<span className="h-3 w-3 rounded-\[3px\] bg-current"/)

assert.doesNotMatch(replyBlocksSource, /停止生成/)
assert.doesNotMatch(replyBlocksSource, />\s*暂停接收\s*</)
assert.match(tutorStreamSource, /const updateCurrent =/)
assert.match(tutorStreamSource, /controllersRef\.current\.get\(requestId\) !== controller/)

console.log("assistant send/stop button assertions passed")
