# 11_API接口设计

## 目录导读

> 本文是当前 API 文档入口，由 FastAPI OpenAPI 自动生成。模块级接口摘要和完整清单保留为独立事实文档；未出现在 OpenAPI 中的旧设计接口均视为未实现。

- 当前模块与接口数量：见“当前模块”。
- 精确端点清单：`16_当前实现API清单.md`。
- 请求和响应 Schema：`docs/assets/api/openapi-current.json` 或运行时 Swagger。
- 文档重新生成：`python scripts/export_implementation_docs.py`。

> 文档状态：**当前实现事实源**
>
> 生成方式：`python scripts/export_implementation_docs.py`
>
> 生成依据：FastAPI `app.openapi()`，共 **90** 个 HTTP 操作。
> 最后同步：2026-06-06

## 使用规则

1. 判断接口是否存在、方法和路径是否正确时，以本文件、`16_当前实现API清单.md` 和 `docs/assets/api/openapi-current.json` 为准。
2. 早期 PRD、设计方案中的接口若未出现在当前清单中，均视为“规划中或未实现”，不得直接调用。
3. 所有业务接口位于 `/api/v1`，成功响应统一包含 `code`、`message`、`data`、`request_id`。
4. 除清单中标记为 Public 的接口外，均要求 JWT Bearer Token。
5. Swagger 运行时入口：`http://127.0.0.1:8000/docs`。

## 当前模块

| 模块 | Tag | HTTP 操作数 | 详细文档 |
|---|---|---:|---|
| 认证与用户 | `auth`, `users` | 8 | `02_认证与用户接口.md` |
| 课程空间 | `courses` | 6 | `03_课程空间接口.md` |
| 资料、知识抽取与检索 | `materials`, `knowledge` | 11 | `04_资料上传与解析接口.md` |
| AI Tutor | `tutor` | 5 | `05_智能问答接口.md` |
| LLM Wiki | `wiki` | 12 | `06_Wiki接口.md` |
| 个性化资源 | `resources` | 6 | `07_资源生成接口.md` |
| 练习与错题 | `quizzes` | 5 | `08_题库练习接口.md` |
| 诊断与推荐 | `diagnosis`, `recommendations` | 9 | `09_学习诊断接口.md` |
| 学习路径与学习记录 | `learning-paths`, `learning-records` | 6 | `10_学习路径推荐接口.md` |
| 学生画像与长期记忆 | `student-profile`, `student-memory` | 9 | `11_学生画像接口.md` |
| Agent 调度与日志 | `agents` | 4 | `12_Agent调度接口.md` |
| 自进化策略 | `evolution` | 6 | `13_自进化策略接口.md` |

## 当前明确未实现

- `/api/v1/admin/*` 管理员后台业务接口。
- `/api/v1/auth/refresh`、`/api/v1/auth/logout`。
- 独立聊天会话与聊天历史列表接口。
- WebSocket 资料处理进度接口。
- 教师端业务接口。

## OpenAPI 快照

- JSON：`docs/assets/api/openapi-current.json`
- 完整端点表：`docs/11_API接口设计/16_当前实现API清单.md`
- 重新生成：`python scripts/export_implementation_docs.py`
