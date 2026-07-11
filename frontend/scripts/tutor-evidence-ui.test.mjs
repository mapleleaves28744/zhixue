import assert from "node:assert/strict"
import fs from "node:fs"

const panel = fs.readFileSync(new URL("../components/assistant/TutorEvidencePanel.tsx", import.meta.url), "utf8")
const page = fs.readFileSync(new URL("../components/assistant/AssistantPageClient.tsx", import.meta.url), "utf8")
const replyBlocks = fs.readFileSync(new URL("../components/assistant/ReplyBlocks.tsx", import.meta.url), "utf8")

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
assert.match(page, /useRag \? \[\] : \["search_course_knowledge", "answer_course_question"\]/)
assert.match(replyBlocks, /preview=\{error \? `回答中断：\$\{error\}` : "暂无内容"\}/)
assert.match(replyBlocks, /error=\{error\}/)

console.log("tutor evidence UI assertions passed")
