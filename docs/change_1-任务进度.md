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

- [ ] 确认 `frontend/public/stitch-pages/stitch-shared.css` 内容完整
- [ ] 确认 `frontend/public/stitch-pages/zhixue-ui.js` 内容完整
- [ ] 复制 IP 贴纸至 `frontend/public/stickers/{zhizhi,lulu,diandian}/`
- [ ] 8 个 Stitch HTML 引用 `stitch-shared.css` + `zhixue-ui.js`，删除重复 glass `<style>`
- [ ] `tailwind.config.ts` 补充 spacing token（gutter、card-gap）
- [ ] **Sprint 1 总验**：`cd frontend; npm run typecheck; npm run build`

### Sprint 1 核验记录

| 任务 | 核验 | 结果 |
|------|------|------|
| （完成后填写） | | |

---

## Sprint 2：API 与 P0 功能

- [ ] 扩展 `zhixue-static-api.js`：`getPageMascot`、401 跳转、与 `ZhixueUI` 协作
- [ ] `/knowledge`：Wiki 详情 `GET /wiki/pages/{id}`，替换静态正文
- [ ] `/knowledge`：Wiki 列表点击切换详情（最小可用）
- [ ] `/practice`：历史诊断 `GET /diagnosis/reports`
- [ ] `/courses`：课程编辑 `PUT /courses/{id}`
- [ ] **Sprint 2 总验**：主链路手动点检 + `npm run typecheck` + `npm run build`

### Sprint 2 核验记录

| 任务 | 核验 | 结果 |
|------|------|------|
| （完成后填写） | | |

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
| | | |
