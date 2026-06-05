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

- [ ] `StitchFrame` 安装 `framer-motion`，路由淡入 ~200ms
- [ ] `scrollReveal` / 区块进入动效在关键页启用
- [ ] **Sprint 3 总验**：路由切换无白屏闪烁；build 通过

### Sprint 3 核验记录

| 任务 | 核验 | 结果 |
|------|------|------|
| （完成后填写） | | |

---

## Sprint 4：IP 与演示抛光

- [ ] `brand-home.html` 使用 `public/brand` IP 图，去除外链占位图
- [ ] 各页空状态使用 `ZhixueUI.emptyState` + 贴纸
- [ ] 编写或更新 `docs/ip-assets/UI集成规范.md`（可选）
- [ ] **Sprint 4 总验**：390/768/1024 三档目视 + 全链路演示

### Sprint 4 核验记录

| 任务 | 核验 | 结果 |
|------|------|------|
| （完成后填写） | | |

---

## 提交记录（change_1）

| 日期 | Commit | 说明 |
|------|--------|------|
| 2026-06-02 | `978fd45` | Sprint 1：共享设计层 + 贴纸 + 8 页引用 |
