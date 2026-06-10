# Phase 2/3 对话式 Agent 任务与规划执行器设计

## 设计结论

Phase 2 和 Phase 3 共用一套持久化任务状态机。Phase 2 负责把自然语言转成受控计划并展示任务卡；Phase 3 负责校验白名单计划、按步骤调用现有 Service、记录进度与产物，并由 ReviewAgent 审查关键输出。

采用同步执行的 PlannerExecutor MVP。`POST /api/v1/agent-tasks/{task_id}/run` 在当前请求内完成计划，后续需要长任务时再替换为后台队列；本阶段不引入 Celery、WebSocket、动态工具调用或任意代码执行。

## 范围

### Phase 2

- 新增 `agent_tasks` 与 `agent_task_steps`。
- 新增 IntentRouterAgent，将自然语言解析为任务类型、目标知识点、目标产物和风险。
- 新增创建、查询、确认、取消、执行与步骤查询 API。
- `/assistant` 对复杂学习任务展示 AgentTask 卡片。

### Phase 3

- 固定计划 Schema 与 agent/action 白名单。
- 新增 `LearningTaskGraph` 同步执行器。
- 复用现有 `LearningPathService`、`ResourceService`、`QuizService`、`RecommendationService` 和 `AgentService`。
- 失败时停止后续步骤，保留已完成步骤与已落库产物。
- `/assistant` 轮询任务与步骤，展示 AgentTimeline 和 artifact 链接摘要。

## 数据模型

`agent_tasks` 保存任务级事实：

- 所属用户与课程。
- 原始输入、IntentRouter 输出、受控计划。
- 风险、确认要求、状态和生命周期时间。
- 失败原因。

`agent_task_steps` 保存执行级事实：

- 固定步骤序号、Agent、action、skill 和预期输出。
- 输入、输出、证据、artifact refs。
- 状态、重试次数、耗时、关联 AgentRun 和失败原因。

所有任务读取必须使用 `task_id + current_user.id` 过滤。课程访问复用 `CourseService.get_readable_course`，因此公有课程可以承载个人任务，但任务和产物仍归当前用户。

## 状态机

任务状态：

```text
planned → running → succeeded
waiting_confirmation → planned → running → succeeded
planned / waiting_confirmation / running → cancelled
running → failed
```

创建时不持久化瞬时 `draft`：Intent 和计划校验成功后直接写入 `planned` 或 `waiting_confirmation`。高风险计划只有确认后才能运行。

步骤状态：

```text
pending → running → succeeded
pending → running → failed
pending → skipped
```

任务失败后尚未执行的步骤标记为 `skipped`。

## Intent 与计划

IntentRouterAgent 使用确定性规则作为 MVP，保证 Mock 和无网络环境下输出稳定。规则识别：

- 学习计划、讲解资料、练习题、课堂讲解等 artifact。
- 图、排序、树、栈、队列、哈希、复杂度等数据结构知识点。
- 删除、覆盖、发布、批量重建、应用自进化策略等高风险动作。

计划只允许以下白名单：

| Agent | action | 调用边界 |
|---|---|---|
| `PlannerAgent` | `generate_learning_path` | `LearningPathService.generate` |
| `ResourceAgent` | `generate_explanation` | `ResourceService.generate_resource` |
| `ResourceAgent` | `generate_html_classroom_draft` | `ResourceService.generate_resource` |
| `QuizAgent` | `generate_quiz` | `QuizService.generate_quiz` |
| `ProfileAgent` | `rebuild_profile_draft` | `ProfileService.rebuild` |
| `RecommendAgent` | `generate_recommendations` | `RecommendationService.refresh_recommendations` |
| `ReviewAgent` | `review_artifacts` | `AgentService.run_task(review_content)` |

不允许从计划字符串动态导入模块、执行 shell、调用未列入白名单的 Agent/action，或绕过 Service 直接写业务表。

## 支持的固定任务

### personalized_learning_package

```text
生成学习路径 → 生成讲解资料 → 生成练习 → Review
```

真实产物至少包括 `learning_path`、`resource`、`quiz`，并记录 Review 结果。

### profile_interview_plan

```text
重建画像草稿 → 刷新推荐 → Review
```

Phase 3 只复用当前画像重建能力；真正的多轮画像访谈属于 Phase 4。

### html_classroom_request

```text
生成 HTML 课堂讲解草稿资源 → Review
```

Phase 3 保存课堂草稿与审查证据；完整交互课堂编辑器属于后续阶段。

## API

```text
POST /api/v1/agent-tasks/create
POST /api/v1/agent-tasks/{task_id}/confirm
POST /api/v1/agent-tasks/{task_id}/run
POST /api/v1/agent-tasks/{task_id}/cancel
GET  /api/v1/agent-tasks/{task_id}
GET  /api/v1/agent-tasks/{task_id}/steps
```

所有 API 使用统一响应结构。非法状态流转返回 `40901`；无权或不存在的任务统一返回 404，避免泄露其他用户任务。

## 前端

保留现有 Stitch `/assistant` 布局。输入包含多个任务 artifact 关键词或明确“帮我生成一套”时，调用 AgentTask API；普通问题仍走 Tutor。

任务卡展示：

- 目标、任务类型、风险、状态。
- 目标知识点和计划产物。
- 确认、开始、取消按钮。
- 步骤时间线、每步证据和 artifact 摘要。

执行期间每 1.5 秒轮询任务与步骤；完成、失败或取消后停止轮询。

## 错误处理与验收

- Intent 或计划无效：不创建任务。
- 单步失败：记录 step error，任务标记 failed，后续步骤 skipped。
- 关键产物必须包含 Review 结果或风险说明。
- 后端测试覆盖 Intent、Schema 白名单、状态机、用户隔离和完整 Mock 执行。
- 数据库执行 migration，前端执行 typecheck/build，并在浏览器实际完成复杂任务创建、运行和时间线验收。

