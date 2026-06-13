import assert from "node:assert/strict"
import fs from "node:fs"

const component = fs.readFileSync(new URL("../components/pet/PetCompanion.tsx", import.meta.url), "utf8")
const layout = fs.readFileSync(new URL("../app/layout.tsx", import.meta.url), "utf8")
const service = fs.readFileSync(new URL("../services/petService.ts", import.meta.url), "utf8")
const assistant = fs.readFileSync(new URL("../components/assistant/AssistantPageClient.tsx", import.meta.url), "utf8")

assert.match(layout, /PetCompanion/)
assert.match(component, /pointermove/)
assert.match(component, /zhixue_pet_position/)
assert.doesNotMatch(component, /const snapped = clampPosition/)
assert.match(component, /localStorage\.setItem\(POSITION_KEY, JSON\.stringify\(current\)\)/)
assert.match(component, /30_000/)
assert.match(component, /prefers-reduced-motion/)
assert.match(service, /student\/pet\/feed/)
assert.match(service, /notifications\/read-all/)
assert.match(assistant, /searchParams\.get\("conversation_id"\)/)

console.log("pet companion contract ok")
