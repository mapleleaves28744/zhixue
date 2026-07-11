import assert from "node:assert/strict"
import fs from "node:fs"

const page = fs.readFileSync(new URL("../components/assistant/AssistantPageClient.tsx", import.meta.url), "utf8")
const panel = fs.readFileSync(new URL("../components/assistant/ResourceSidePanel.tsx", import.meta.url), "utf8")
const dialog = fs.readFileSync(new URL("../components/assistant/ResourcePanelDialog.tsx", import.meta.url), "utf8")

assert.match(page, /hidden xl:block/)
assert.match(page, /xl:hidden/)
assert.match(page, /ResourcePanelDialog/)
assert.match(page, /课程加载失败/)
assert.doesNotMatch(panel, /h-full w-full lg:w-\[360px\]/)
assert.match(dialog, /max-xl:bottom-0/)
assert.match(dialog, /md:right-0/)

console.log("assistant responsive layout assertions passed")
