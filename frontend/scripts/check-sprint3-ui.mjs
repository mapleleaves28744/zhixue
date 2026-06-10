import { fileURLToPath } from "node:url";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

const root = fileURLToPath(new URL("..", import.meta.url));

async function readProjectFile(path) {
  return readFile(join(root, path), "utf8");
}

function assertIncludes(source, needle, label) {
  if (!source.includes(needle)) {
    throw new Error(`${label}: expected to find ${needle}`);
  }
}

const packageJson = JSON.parse(await readProjectFile("package.json"));
if (!packageJson.dependencies?.["framer-motion"]) {
  throw new Error("package.json: framer-motion dependency is required for Sprint 3 shell motion");
}

const stitchFrame = await readProjectFile("components/StitchFrame.tsx");
assertIncludes(stitchFrame, '"use client"', "StitchFrame");
assertIncludes(stitchFrame, "framer-motion", "StitchFrame");
assertIncludes(stitchFrame, "AnimatePresence", "StitchFrame");
assertIncludes(stitchFrame, "duration: 0.2", "StitchFrame");
assertIncludes(stitchFrame, "key={src}", "StitchFrame");

const sharedUi = await readProjectFile("public/stitch-pages/zhixue-ui.js");
assertIncludes(sharedUi, "DEFAULT_REVEAL_SELECTORS", "zhixue-ui");
assertIncludes(sharedUi, "initScrollReveal", "zhixue-ui");
assertIncludes(sharedUi, "Node.ELEMENT_NODE", "zhixue-ui");

const sharedCss = await readProjectFile("public/stitch-pages/stitch-shared.css");
assertIncludes(sharedCss, "@media (prefers-reduced-motion: reduce)", "stitch-shared.css");
assertIncludes(sharedCss, ".reveal-on-scroll.is-visible", "stitch-shared.css");

console.log("Sprint 3 UI checks passed");
