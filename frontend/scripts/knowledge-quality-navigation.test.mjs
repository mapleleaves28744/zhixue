import assert from "node:assert/strict"
import fs from "node:fs"

const api = fs.readFileSync(new URL("../public/stitch-pages/zhixue-static-api.js", import.meta.url), "utf8")
const knowledge = fs.readFileSync(new URL("../public/stitch-pages/knowledge.html", import.meta.url), "utf8")
const dashboard = fs.readFileSync(new URL("../public/stitch-pages/dashboard.html", import.meta.url), "utf8")

assert.match(api, /function getCourseQualityReport\(courseId\)/)
assert.match(api, /knowledge\/seed-quality-report\?\$\{query\}/)
assert.match(knowledge, /api\.getCourseQualityReport\(currentCourseId\)/)
assert.match(knowledge, /content_quality/)
assert.match(knowledge, /needs_enrichment/)
assert.match(knowledge, /pendingWikiPageId/)
assert.match(knowledge, /pendingGraphKnowledgeId/)
assert.match(dashboard, /onNodeClick\(node\)/)
assert.match(dashboard, /tab=wiki/)
assert.match(dashboard, /page_id=/)
assert.match(dashboard, /tab=graph/)
assert.match(dashboard, /knowledge_id=/)

console.log("knowledge quality and graph navigation contract ok")
