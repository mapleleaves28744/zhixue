import fs from "node:fs";
import path from "node:path";

const root = process.cwd().endsWith("frontend") ? path.resolve("..") : process.cwd();

const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), "utf8");

const assistantPage = read("frontend/app/assistant/page.tsx");
const assistantClient = read("frontend/components/assistant/AssistantPageClient.tsx");
const markdownRenderer = read("frontend/components/markdown/MarkdownRenderer.tsx");
const streamLine = read("frontend/components/assistant/StreamActivityLine.tsx");
const historyHover = read("frontend/components/assistant/ConversationHistoryHover.tsx");
const knowledge = read("frontend/public/stitch-pages/knowledge.html");
const home = read("frontend/public/stitch-pages/home.html");
const staticApi = read("frontend/public/stitch-pages/zhixue-static-api.js");
const packageJson = JSON.parse(read("frontend/package.json"));

const checks = [
  ["助手页不再使用 StitchFrame", !assistantPage.includes("StitchFrame")],
  ["助手页挂载 React Client", assistantPage.includes("AssistantPageClient")],
  ["快速/智能体模式切换", assistantClient.includes("ModeToggle")],
  ["Tutor 流式 hook", assistantClient.includes("useTutorStream")],
  ["Agent 回复块", assistantClient.includes("AgentReplyBlock")],
  ["Tutor 回复块", assistantClient.includes("TutorReplyBlock")],
  ["Agent 事件详情", read("frontend/components/assistant/AgentEventDetail.tsx").includes("reasoning_content")],
  ["Agent 内联兜底配置", read(".env.example").includes("AGENT_INLINE_FALLBACK")],
  ["Agent 详情弹窗", assistantClient.includes("ActivityDetailDialog")],
  ["对话历史悬停", historyHover.includes("onMouseEnter") && assistantClient.includes("ConversationHistoryHover")],
  ["单行流式摘要", streamLine.includes("truncate")],
  ["工具选择 chip", assistantClient.includes("ToolSelector")],
  ["Markdown 渲染组件", markdownRenderer.includes("react-markdown")],
  ["资源侧栏持久化", assistantClient.includes("ResourceSidePanel")],
  ["知识库资料下载/预览/切片", knowledge.includes("material-download") && knowledge.includes("material-view-chunks")],
  ["知识库不再暴露 parsed_text_path", !knowledge.includes("文本缓存：${escapeHtml(parsedPath)}")],
  ["首页快捷提问跳转助手", home.includes("home-assistant-question") && home.includes("/assistant?question=")],
  ["静态 API 暴露 material chunks", staticApi.includes("listMaterialChunks")],
  ["markdown 依赖已安装", Boolean(packageJson.dependencies["react-markdown"])],
];

const failed = checks.filter(([, passed]) => !passed);
for (const [name, passed] of checks) {
  console.log(`${passed ? "PASS" : "FAIL"}: ${name}`);
}
if (failed.length) process.exit(1);
