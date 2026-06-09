import fs from "node:fs";

const practice = fs.readFileSync("frontend/public/stitch-pages/practice.html", "utf8");
const knowledge = fs.readFileSync("frontend/public/stitch-pages/knowledge.html", "utf8");

const checks = [
  ["练习配置表单有稳定容器", practice.includes('id="practice-config-section"')],
  ["生成题目渲染到表单下方", practice.includes("const resultSection = container.querySelector('#quiz-result-section')")],
  ["生成后保持练习生成高亮", practice.includes("setPracticeTabActive('练习生成')")],
  ["答题竞技保留独立答题模式", practice.includes("quizRenderMode = 'standalone'")],
  ["知识库 Tab 使用显式状态标识", knowledge.includes('data-knowledge-tab="课程 Wiki"')],
  ["Wiki 详情有明确返回按钮", knowledge.includes("返回 Wiki 列表")],
  ["知识图谱调用真实接口", knowledge.includes("getWikiGraph") || knowledge.includes("/wiki/graph")],
  ["知识图谱使用 D3 力导向组件", knowledge.includes("ZhixueForceGraph") && knowledge.includes("d3.min.js")],
  ["力导向图支持悬停知识点提示", fs.readFileSync("frontend/public/stitch-pages/zhixue-force-graph.js", "utf8").includes("zhixue-graph-tooltip")],
  ["力导向图按掌握度区分颜色与大小", fs.readFileSync("frontend/public/stitch-pages/zhixue-force-graph.js", "utf8").includes("masteryRadius") && fs.readFileSync("frontend/public/stitch-pages/zhixue-force-graph.js", "utf8").includes("#16a34a")],
  ["知识图谱节点可打开 Wiki", knowledge.includes('data-wiki-page-id="${node.id}"') || knowledge.includes("data-wiki-page-id")],
  ["图谱 Tab 已绑定渲染", knowledge.includes('label === "图谱视图"') && knowledge.includes("renderWikiGraph()")],
  ["知识库支持课程切换", knowledge.includes("knowledge-course-select") && knowledge.includes("syncCourseSelector")],
  ["图谱空状态区分资料与 Wiki", knowledge.includes("图谱节点来自 Wiki") && knowledge.includes("从资料生成 Wiki")],
  ["资料可下载预览切片", knowledge.includes("material-download") && knowledge.includes("material-view-chunks")],
  ["Wiki Markdown 增强渲染", knowledge.includes("ZhixueUI.renderMarkdown")],
];

const failed = checks.filter(([, passed]) => !passed);
for (const [name, passed] of checks) {
  console.log(`${passed ? "PASS" : "FAIL"}: ${name}`);
}
if (failed.length) process.exit(1);
