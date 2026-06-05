import { fileURLToPath } from "node:url";
import { access, readFile } from "node:fs/promises";
import { join } from "node:path";

const frontendRoot = fileURLToPath(new URL("..", import.meta.url));
const repoRoot = join(frontendRoot, "..");

async function readFrontend(path) {
  return readFile(join(frontendRoot, path), "utf8");
}

async function readRepo(path) {
  return readFile(join(repoRoot, path), "utf8");
}

function assertIncludes(source, needle, label) {
  if (!source.includes(needle)) {
    throw new Error(`${label}: expected to find ${needle}`);
  }
}

await access(join(frontendRoot, "public/stickers/zhizhi/05_sleepy_idle.png"));
await access(join(frontendRoot, "public/stickers/diandian/05_sleepy_idle.png"));
await access(join(frontendRoot, "public/stickers/lulu/05_sleepy_idle.png"));

const sharedUi = await readFrontend("public/stitch-pages/zhixue-ui.js");
assertIncludes(sharedUi, "emptyStateHtml", "zhixue-ui");
assertIncludes(sharedUi, "renderEmptyState", "zhixue-ui");

const pageExpectations = [
  ["courses", "emptyState"],
  ["practice", "emptyState"],
  ["assistant", "emptyState"],
  ["path-profile", "emptyState"],
  ["home", "emptyState"],
  ["knowledge", "renderEmptyState"],
];

for (const [page, needle] of pageExpectations) {
  const source = await readFrontend(`public/stitch-pages/${page}.html`);
  if (needle === "emptyState") {
    assertIncludes(source, "ZhixueUI", `${page}.html`);
  }
  assertIncludes(source, needle, `${page}.html`);
}

const guide = await readRepo("docs/ip-assets/UI集成规范.md");
["/knowledge", "/assistant", "/practice", "/dashboard", "/path-profile", "ZhixueUI.emptyState"].forEach((needle) => {
  assertIncludes(guide, needle, "UI集成规范.md");
});

console.log("Sprint 4 IP checks passed");
