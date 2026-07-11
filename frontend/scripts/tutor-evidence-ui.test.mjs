import assert from "node:assert/strict"
import fs from "node:fs"

const panel = fs.readFileSync(new URL("../components/assistant/TutorEvidencePanel.tsx", import.meta.url), "utf8")
const page = fs.readFileSync(new URL("../components/assistant/AssistantPageClient.tsx", import.meta.url), "utf8")

for (const token of [
  "grounding_status",
  "课程依据不足",
  "citation.quote",
  "follow_up_questions",
  "submitTutorFeedback",
  "saveTutorAnswerToWiki",
]) {
  assert.match(panel, new RegExp(token))
}
assert.match(page, /learning_record_id/)
assert.match(page, /related_knowledge_points/)
assert.match(page, /follow_up_questions/)

console.log("tutor evidence UI assertions passed")
