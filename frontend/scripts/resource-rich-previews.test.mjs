import assert from "node:assert/strict"
import fs from "node:fs"

const preview = fs.readFileSync(
  new URL("../components/assistant/ResourcePreviewBody.tsx", import.meta.url),
  "utf8",
)
const mermaid = fs.readFileSync(new URL("../lib/mermaid.ts", import.meta.url), "utf8")
const diagram = fs.readFileSync(
  new URL("../components/assistant/MermaidDiagram.tsx", import.meta.url),
  "utf8",
)

assert.match(preview, /FlashcardDeck/)
assert.match(preview, /resource_type === "flashcard"/)
assert.match(mermaid, /resource\.resource_type === "mindmap"[\s\S]*isMermaidContent/)
assert.match(diagram, /themeVariables/)

console.log("rich resource preview contracts passed")
