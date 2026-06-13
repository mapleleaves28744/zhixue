import assert from "node:assert/strict"
import fs from "node:fs"
import { createRequire } from "node:module"
import path from "node:path"
import vm from "node:vm"
import ts from "typescript"

const root = path.resolve(import.meta.dirname, "..")
const sourcePath = path.join(root, "components", "assistant", "agentTimelineSteps.ts")
const require = createRequire(import.meta.url)

function loadTimelineModule() {
  const source = fs.readFileSync(sourcePath, "utf8")
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      esModuleInterop: true,
    },
  }).outputText
  const module = { exports: {} }
  const context = vm.createContext({
    exports: module.exports,
    module,
    require,
  })
  vm.runInContext(compiled, context, { filename: sourcePath })
  return module.exports
}

const { buildAgentStepTimeline } = loadTimelineModule()

const events = [
  {
    type: "plan_created",
    data: {
      summary: "围绕栈和队列生成学习资源",
      plan: ["检索课程资料", "生成练习题"],
      tool_calls: [
        { name: "search_course_knowledge", arguments: { query: "栈 队列" } },
        { name: "generate_quiz", arguments: { count: 5 } },
      ],
    },
  },
  {
    type: "tool_started",
    data: { tool_name: "search_course_knowledge", arguments: { query: "栈 队列" } },
  },
  {
    type: "tool_completed",
    data: { tool_name: "search_course_knowledge", success: true, attempts: 1 },
  },
  {
    type: "observation",
    data: { tool_name: "search_course_knowledge", output: { summary: "找到 3 条资料引用" } },
  },
  {
    type: "multimodal_progress",
    data: { stage: "video_queued", message: "课堂视频已进入后台导出", progress: 35 },
  },
  {
    type: "completed",
    data: { final_answer: "已完成" },
  },
]

const steps = buildAgentStepTimeline(events, false)

assert.equal(steps.length, 4)
assert.equal(steps[0].title, "查看 2 个步骤")
assert.equal(steps[0].status, "complete")
assert.equal(steps[1].title, "执行 search_course_knowledge")
assert.equal(steps[1].status, "complete")
assert.match(steps[1].detailText, /query/)
assert.equal(steps[2].title, "课堂视频已进入后台导出")
assert.equal(steps[2].status, "running")
assert.equal(steps.at(-1).title, "回答已生成")

const streamingSteps = buildAgentStepTimeline(events.slice(0, 2), true)
assert.equal(streamingSteps.at(-1).status, "running")

const duplicateProgressEvents = [
  { type: "multimodal_progress", data: { job_id: "job-1", stage: "generating_outlines", message: "Generating scene outlines", progress: 15 } },
  { type: "multimodal_progress", data: { job_id: "job-1", stage: "generating_outlines", message: "Generated 8 scene outlines", progress: 30 } },
  { type: "multimodal_progress", data: { job_id: "job-1", stage: "generating_outlines", message: "Generated 8 scene outlines", progress: 30 } },
]
const dedupedSteps = buildAgentStepTimeline(duplicateProgressEvents, true)
assert.equal(dedupedSteps.length, 1)
assert.equal(dedupedSteps[0].subtitle, "generating_outlines · 30%")
assert.equal(dedupedSteps[0].status, "running")

console.log("agent-step-timeline assertions passed")
