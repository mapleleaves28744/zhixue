# change_6 与 change_7 合并验收记录

> 验收日期：2026-07-11
>
> 合并目标：将 `change_7` 的 Grounded QA、可信引用和助手体验优化应用到基于远程 `origin/change_6` 的本地 `change_6`。

## 分支关系

- 共同基线：`82051d0`（`change_5`）。
- 远程 change_6 合并前 HEAD：`3a37fc2`，相对共同基线独有 4 个提交。
- 本地 change_7 HEAD：`d280bf7`，相对共同基线独有 15 个提交。
- 合并采用三方 merge，不是 fast-forward；当前只完成本地合并，未推送远程。

原工作区中的 `deploy/ssh-cursor-proxy.config.example` 本地修改单独保存在 Git stash `preserve-local-ssh-config-before-change6-change7-merge`，未进入任一分支或合并提交。

## 冲突与取舍

共解决 7 个文本冲突：

1. `supervisor.py`、`supervisor_intents.py`：保留 change_6 的推荐、诊断、联网搜索、多意图和资源交付安全网；纯课程问答使用 `answer_course_question`，纯检索使用 `search_course_knowledge`。
2. `mock_provider.py`：同时保留互动课件 Mock 与 Grounded Tutor 的编号引用和无依据拒答。
3. `tutor_service.py`：普通课程问答进入 Grounded QA；联网问答保留 AnySearch 专用流程。
4. `test_agent_runtime.py`：保留双方测试，并补充联网问答不回落课程 RAG、关闭资料库不强制 Grounded QA 的回归测试。
5. 两份当前实现事实文档：保留 change_6 新能力，同时加入 change_7 的严格评测结果与限制。

审查阶段额外修复：

- “联网搜索并解释”不再执行 `search_web` 后又被课程 RAG 覆盖；最终回答直接使用联网结果。
- Agent 模式关闭资料库时，同时跳过 `search_course_knowledge` 和复合工具 `answer_course_question`。
- Tutor 在首个增量前失败且没有正文时，会展示具体错误，而不是只显示“暂无内容”。
- 外部资源 feed 单测显式注入启用的 WebSearchService，消除对本机 API Key 配置的依赖。

## 合并前基线

原始 `origin/change_6` 存在两项可复现阻塞，均由 change_7 修复：

- 后端测试收集因 `backend/app/storage/local_storage.py` 被宽泛 `.gitignore` 规则排除而失败。
- Next.js 16 类型检查因 `/login` 使用同步 `searchParams` 类型而失败。

文档检查在合并前通过。

## 合并后验证

| 检查 | 结果 |
|---|---|
| `cd backend; python -m pytest tests -q` | 442 passed，6 个既有 FastAPI `on_event` 弃用警告 |
| `cd backend; python -m compileall -q app tests` | 通过 |
| 5 个 Assistant Node 契约脚本 | 通过 |
| `cd frontend; npm run typecheck` | 通过 |
| `cd frontend; npx next build --webpack` | 通过 |
| `python scripts/export_implementation_docs.py` | 147 个 API 操作、44 个数据库表 |
| `python scripts/check_docs.py` | 通过，无占位和本地断链 |
| `git diff --check` | 通过 |

本次合并没有新增数据库结构或 Alembic migration。Grounded QA 的 Mock 严格引用精度和覆盖率仍未达到理想目标，真实 Provider 与人工正确率评分仍属于后续质量优化，不因分支合并而视为完成。
