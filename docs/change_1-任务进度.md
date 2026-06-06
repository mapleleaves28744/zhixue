# change_1 分支任务进度

| 项目 | 说明 |
|------|------|
| 分支 | `change_1` |
| 基准 | `main` @ 文档提交后 |
| 开始日期 | 2026-06-02 |
| 参考文档 | [`前端高级化升级方案.md`](前端高级化升级方案.md)、[`功能完成度与待完善清单.md`](功能完成度与待完善清单.md) |

**核验约定**：每完成一项，在「核验记录」填写命令/结果，再将 `[ ]` 改为 `[x]`。

---

## Sprint 1：设计基座统一

- [x] 确认 `frontend/public/stitch-pages/stitch-shared.css` 内容完整
- [x] 确认 `frontend/public/stitch-pages/zhixue-ui.js` 内容完整
- [x] 复制 IP 贴纸至 `frontend/public/stickers/{zhizhi,lulu,diandian}/`
- [x] 8 个 Stitch HTML 引用 `stitch-shared.css` + `zhixue-ui.js`，删除重复 glass `<style>`
- [x] `tailwind.config.ts` 补充 spacing token（gutter、card-gap）
- [x] **Sprint 1 总验**：`cd frontend; npm run typecheck; npm run build`

### Sprint 1 核验记录

| 任务 | 核验 | 结果 |
|------|------|------|
| stitch-shared.css | 人工审阅：含 glass、动效、auth/modal、empty、agent-timeline 等 | 通过；补充 `.zhixue-field`、`.mask-gradient`、`.body-practice-bg` |
| zhixue-ui.js | 人工审阅：skeleton、emptyState、toast、scrollReveal、getPageMascot | 通过 |
| IP 贴纸 | `Get-ChildItem frontend/public/stickers -Recurse -Filter *.png` | 36 个 PNG（每角色 12 张） |
| 8 页引用共享层 | `rg stitch-shared.css frontend/public/stitch-pages/*.html` | 8/8 命中；已移除页内重复 `<style>` |
| tailwind spacing | `npm run typecheck` | 通过 |
| Sprint 1 总验 | `npm run typecheck` + `npm run build` | 均通过（Next.js 14.2.35） |

---

## Sprint 2：API 与 P0 功能

- [x] 扩展 `zhixue-static-api.js`：`getPageMascot`、`getWikiPage`、`updateCourse`、401 品牌页登录跳转、与 `ZhixueUI` 协作
- [x] `/knowledge`：Wiki 详情 `GET /wiki/pages/{id}`，替换静态正文并展示来源、版本、AI 推断提示
- [x] `/knowledge`：Wiki 列表点击切换详情（最小可用），无页面时展示真实空状态
- [x] `/practice`：历史诊断 `GET /diagnosis/reports` 优先展示；无历史时再引导运行分析
- [x] `/courses`：课程编辑 `PUT /courses/{id}`，公共课程保持只读提示
- [x] **Sprint 2 总验**：主链路手动点检 + `npm run typecheck` + `npm run build`

### Sprint 2 执行口径修正

1. 本 Sprint 优先补真实 API 联动，不做全站重排和大范围动效。
2. `StitchFrame` 的 `framer-motion` 路由淡入、品牌页 IP 海报和外链图清理后移到 Sprint 3/4。
3. 每个勾选项必须至少满足：真实接口已调用、空状态/错误态可见、构建检查通过；涉及页面交互的项还需浏览器点检。
4. 若后端接口存在但 Stitch 页面未接，不得宣称对应功能完成。

### Sprint 2 核验记录

| 任务 | 核验 | 结果 |
|------|------|------|
| 共享 API | 代码审阅 + 内联脚本语法检查 | 通过；新增 Wiki 详情、版本、课程更新、401 品牌页登录跳转 |
| `/knowledge` Wiki 详情 | 浏览器未登录烟测 + DOM 检查 | 通过基础加载；点击 Wiki Tab 可进入真实空状态。完整详情需登录态与真实 Wiki 数据继续点检 |
| `/practice` 历史诊断 | 浏览器未登录烟测 | 通过基础加载；未登录时展示“历史诊断加载失败”，登录后应显示 `GET /diagnosis/reports` 历史列表 |
| `/courses` 编辑课程 | 浏览器未登录烟测 + 创建弹窗检查 | 创建/编辑共用弹窗脚本通过；无课程数据时未出现编辑按钮，需登录后用真实课程点检 PUT |
| Sprint 2 登录态总验 | 浏览器 E2E：注册临时学生账号 → 创建课程 → 编辑课程 → API 上传资料并生成 Wiki → 页面点击 Wiki 详情 → 生成练习 → 提交答案 → 运行诊断 → 回到历史诊断列表 | 通过；课程标题更新为“已编辑”，Wiki 详情显示正文/来源/版本/AI 核对提示，诊断历史显示新报告、100% 正确率和 Agent 生成标记 |
| 前端构建 | `npm run build` | 通过（Next.js 14.2.35；普通沙箱因 worker spawn EPERM，提升权限后通过） |
| 类型检查 | `npm run typecheck` | 通过 |

---

## Sprint 3：动效与壳层

- [x] `StitchFrame` 安装 `framer-motion`，路由淡入 ~200ms
- [x] `scrollReveal` / 区块进入动效在关键页启用
- [x] **Sprint 3 总验**：路由切换无白屏闪烁；build 通过

### Sprint 3 核验记录

| 任务 | 核验 | 结果 |
|------|------|------|
| Sprint 3 静态检查 | `node scripts/check-sprint3-ui.mjs` | 通过；校验 Framer 壳层、200ms 过渡、scrollReveal 防御逻辑与 reduced motion |
| 类型检查 | `npm run typecheck` | 通过 |
| 前端构建 | `npm run build` | 通过（Next.js 14.2.35） |
| Stitch 动效烟测 | 浏览器直开 `/stitch-pages/{practice,knowledge,dashboard,courses}.html` | 通过；`reveal-on-scroll` 已注入，当前时间之后无新增 console error |
| 路由切换烟测 | 浏览器依次访问 `/practice`、`/knowledge`、`/dashboard`、`/courses`、`/practice` | 通过；iframe 尺寸稳定，shell opacity 最终为 1，当前时间之后无新增 console error |

---

## Sprint 4：IP 与演示抛光

- [x] `brand-home.html` 使用 `public/brand` IP 图，去除外链占位图
- [x] 各页空状态使用 `ZhixueUI.emptyState` + 贴纸
- [x] 编写或更新 `docs/ip-assets/UI集成规范.md`（可选）
- [x] **Sprint 4 总验**：390/768/1024 三档目视 + 全链路演示

### Sprint 4 核验记录

| 任务 | 核验 | 结果 |
|------|------|------|
| 品牌页 IP 图 | `rg -n "googleusercontent|aida-public" frontend/public/stitch-pages --glob "*.html"` | 通过；`brand-home.html` 主视觉改用本地 IP 单体图，知识图谱图位恢复旧视觉并本地化到 `public/brand` |
| 其余外链图清理 | 同上 + 代码审阅 | 通过；`home.html`、`courses.html` 残留外链装饰图已替换为本地品牌 IP 资产 |
| 空状态 IP 化 | `node scripts/check-sprint4-ip.mjs` | 通过；课程、练习、助手、首页、路径画像等关键空状态已接 `ZhixueUI.emptyState` / `renderEmptyState` |
| IP 集成规范 | 人工审阅 `docs/ip-assets/UI集成规范.md` | 已补页面 mascot 映射、贴纸 scene 用途、实现约定和当前接入范围 |
| Sprint 4 视口总验 | Playwright CLI：390/768/1024 视口截图 `/`、`/practice`、`/path-profile` | 通过；截图保存在 `%TEMP%/zhixue-sprint4-viewports`，抽检未见白屏、图片缺失或明显文字压缩 |

---

## 主链路稳定性与安全专项

- [x] 新增真实 LLM 主链路验收脚本，覆盖资料上传到 Agent 日志的 23 个步骤
- [x] 使用 `xiaomi_mimo / mimo-v2.5` 实际跑通，`fallback_used=false`
- [x] 后端 pytest、Alembic、前端 typecheck/build 通过
- [x] Next.js 14.2.35 升级到 16.2.7，PostCSS 统一到 8.5.15
- [x] `npm audit --audit-level=moderate` 归零
- [x] 更新 README、阶段验收清单与专项验收记录

### 专项核验记录

| 任务 | 核验 | 结果 |
|------|------|------|
| 真实 LLM 整链 | `python scripts/main_chain_check.py` | 23 步通过；生成 5 个知识点、5 个 Wiki 页面、3 道练习、1 份诊断、1 条自进化策略；Agent 日志 6 条 |
| 真实 Provider | Tutor 响应元数据 | `provider=xiaomi_mimo`、`model=mimo-v2.5`、`fallback_used=false` |
| 后端与数据库 | `python -m pytest -q`、`python -m alembic upgrade head` | 91 passed；migration head 通过 |
| 前端安全升级 | `npm run typecheck`、`npm run build`、`npm audit --audit-level=moderate` | Next.js 16.2.7 构建通过；0 vulnerabilities |
| Next 16 浏览器烟测 | 品牌首页 + 6 个关键 Stitch 页面逐页加载 | 通过；逐页导航未新增控制台错误 |

---

## 文档事实源校准专项

- [x] 建立当前实现基线和文档状态优先级
- [x] 从 FastAPI OpenAPI 自动生成当前 API 文档与接口清单
- [x] 从 SQLAlchemy metadata 自动生成当前数据库清单
- [x] 按当前 Stitch 页面架构更新前端页面与路由文档
- [x] 更新功能完成度、系统架构与各目标设计文档的状态说明
- [x] 在 `AGENTS.md` 中加入事实源读取和文档同步规则

### 专项核验记录

| 任务 | 核验 | 结果 |
|------|------|------|
| API 文档同步 | `python scripts/export_implementation_docs.py` | 通过；导出 89 个 HTTP 操作与 OpenAPI 当前快照 |
| 数据库文档同步 | 同上 | 通过；导出 28 张 ORM 表 |
| 同步脚本语法 | `python -m py_compile scripts/export_implementation_docs.py` | 通过 |
| 文档格式检查 | `git diff --check` | 通过 |
| 项目回归 | `scripts/local_check.ps1 -All` | 通过；Alembic head、91 个后端测试、FastAPI import、前端 typecheck/build 均通过 |

---

## 提交记录（change_1）

| 日期 | Commit | 说明 |
|------|--------|------|
| 2026-06-02 | `978fd45` | Sprint 1：共享设计层 + 贴纸 + 8 页引用 |
| 2026-06-05 | `fdbf630` | Sprint 2：课程编辑、Wiki 详情、历史诊断总验链路 |
| 2026-06-05 | `1098ac0` | Sprint 3/4 前置视觉小修：外链图本地化、知识图谱旧图恢复 |
| 2026-06-05 | `21809c2` | Sprint 3：StitchFrame 路由淡入、scrollReveal 与壳层稳定性 |
| 2026-06-06 | `aab1343` | 真实 LLM 整链验收与 Next.js 安全升级 |
