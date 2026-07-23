import assert from "node:assert/strict"
import fs from "node:fs"

const historyPanel = fs.readFileSync(
  new URL("../components/assistant/ConversationHistoryHover.tsx", import.meta.url),
  "utf8",
)
const assistant = fs.readFileSync(
  new URL("../components/assistant/AssistantPageClient.tsx", import.meta.url),
  "utf8",
)

// The record entry must be usable with mouse, keyboard, and touch; hover-only
// controls make the panel disappear while the learner is trying to select it.
assert.match(historyPanel, /onClick=\{\(\) => setOpen\(\(value\) => !value\)\}/)
assert.doesNotMatch(historyPanel, /onMouseEnter=\{\(\) => setOpen\(true\)\}/)
assert.match(historyPanel, /学习记录/)
assert.match(historyPanel, /listResources/)
assert.match(historyPanel, /onOpenResources/)
assert.match(historyPanel, /normalizeResourceType\(resource\.resource_type\)/)
assert.doesNotMatch(assistant, /resourceFocusId/)

// A persisted user message already owns the task id.  History hydration must
// rebuild its Agent status card even when a task is still running or failed and
// therefore has not yet written an assistant message.
assert.match(assistant, /taskId: m\.task_id/)
assert.match(assistant, /const agentMessageByTaskId = new Map<string, number>\(\)/)

console.log("assistant learning records contracts passed")
