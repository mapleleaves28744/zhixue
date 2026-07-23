import assert from "node:assert/strict"
import fs from "node:fs"
import vm from "node:vm"

const source = fs.readFileSync(new URL("../public/stitch-pages/path-profile.html", import.meta.url), "utf8")
const match = source.match(/  function resolveMasteryPresentation\([\s\S]*?\n  \}\n\n  function renderCoursePortraitBlock/)

assert.ok(match, "expected resolveMasteryPresentation helper")
const helper = match[0].replace(/\n\n  function renderCoursePortraitBlock$/, "")
const context = {}
vm.runInNewContext(`${helper}\nglobalThis.resolveMasteryPresentation = resolveMasteryPresentation`, context)

const legacy = context.resolveMasteryPresentation(
  { mastery_snapshot: { _overall_percent: 1 } },
)
assert.equal(JSON.stringify(legacy), JSON.stringify({
  score: 50,
  label: "待验证",
  detail: "尚无有效学习证据，先以中性基线展示。",
}))

const evidenceBacked = context.resolveMasteryPresentation(
  {
    mastery_snapshot: {
      _algorithm_version: "evidence_weighted_v2",
      _overall: 0.63,
      _evidence_count: 4,
      _confidence: 0.44,
      _status: "building_evidence",
    },
  },
)
assert.equal(JSON.stringify(evidenceBacked), JSON.stringify({
  score: 63,
  label: "正在建立",
  detail: "已基于 4 条有效学习证据动态更新（置信度 44%）。",
}))

console.log("profile mastery presentation contract ok")
