import assert from "node:assert/strict"
import fs from "node:fs"

const service = fs.readFileSync(new URL("../services/tutorService.ts", import.meta.url), "utf8")
const hook = fs.readFileSync(new URL("../hooks/useTutorStream.ts", import.meta.url), "utf8")
const page = fs.readFileSync(new URL("../components/assistant/AssistantPageClient.tsx", import.meta.url), "utf8")

assert.match(service, /let receivedDelta = false/)
assert.match(service, /let receivedDone = false/)
assert.match(service, /if \(!receivedDelta\)/)
assert.match(service, /\{ \.\.\.payload, stream: false \}/)
assert.match(service, /if \(!receivedDone\)/)
assert.match(service, /onInterrupted/)
assert.match(service, /eventName === "evidence"/)
assert.match(hook, /Record<string, TutorStreamSnapshot>/)
assert.match(hook, /const stopAll = useCallback/)
assert.doesNotMatch(page, /import \{ streamTutorChat \}/)
assert.match(page, /useTutorStream/)

console.log("tutor stream policy assertions passed")
