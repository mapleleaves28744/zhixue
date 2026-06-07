# Phase 2 与 Phase 3 Agent 任务执行器阶段验收记录

> 验收日期：2026-06-07  
> 验收分支：`change_2`  
> 验收环境：本机 PostgreSQL、FastAPI、Next.js、Mock LLM 浏览器执行验收；Docker 不属于本阶段范围。  
> 验收结论：**Phase 2 对话式 Agent 任务入口与 Phase 3 Agent 规划执行器 MVP 均通过验收，状态为 completed。**

## 验收范围

本次验收覆盖自然语言任务理解、AgentTask/Step 持久化、任务状态机、用户隔离、计划白名单、高风险确认、固定计划执行、现有 Service 复用、ReviewAgent、失败保留、`/assistant` AgentTask 卡片与轮询时间线。

本阶段执行器是受控固定计划 MVP，不允许动态导入、任意 action、shell 命令或开放式自治工具调用。后台队列、SSE 和可暂停/恢复的长任务属于后续增强。

## 实际实现

### Phase 2

- 新增 `agent_tasks`、`agent_task_steps` 两张表及 Alembic migration。
- 新增 `IntentRouterAgent`，可解析 task type、目标知识点、artifact、风险和确认要求。
- 新增 6 个 AgentTask API：创建、详情、步骤、确认、执行、取消。
- 所有任务查询按当前用户过滤，课程读取复用 `CourseService.get_readable_course`。
- `/assistant` 可自动区分普通 Tutor 问题与复杂 Agent 学习任务。

### Phase 3

- 新增 `AgentTaskPlan` / `AgentTaskPlanStep` Schema 和精确 agent/action 白名单。
- 新增 `LearningTaskGraph`，通过现有 Service 执行固定计划。
- `personalized_learning_package` 可真实生成学习路径、讲解资源、练习和 Review 结果。
- 支持 `profile_interview_plan` 和 `html_classroom_request` 固定计划。
- 单步失败时保留已完成产物，当前步骤标记 failed，剩余步骤标记 skipped。
- `/assistant` 使用轮询展示 pending/running/succeeded/failed/skipped 时间线。

## 数据库与 API

| 项目 | 验收结果 |
|---|---:|
| ORM 表 | 30 |
| Alembic migration | 18 |
| FastAPI HTTP 操作 | 96 |
| Agent 类 | 14，新增 `IntentRouterAgent` |
| AgentTask API | 6 |

新增 API：

```text
POST /api/v1/agent-tasks/create
GET  /api/v1/agent-tasks/{task_id}
GET  /api/v1/agent-tasks/{task_id}/steps
POST /api/v1/agent-tasks/{task_id}/confirm
POST /api/v1/agent-tasks/{task_id}/run
POST /api/v1/agent-tasks/{task_id}/cancel
```

## Mock 完整执行验收

使用公有《数据结构》课程执行：

```text
我最近图和排序不太会，帮我生成一套学习计划、讲解资料和练习题。
```

结果：

```text
task_type: personalized_learning_package
status: planned → running → succeeded
steps: 4 / 4 succeeded
artifacts: learning_path、resource、quiz、review_result
```

数据库中本阶段验收任务：

| 指标 | 结果 |
|---|---:|
| AgentTask 数 | 3 |
| succeeded | 2 |
| 最新浏览器任务 ID | `44ad4b56-2552-47c0-8e0c-f3ff4381c45d` |
| 最新任务步骤 | 4 个，全部 succeeded |

最新浏览器任务步骤耗时：

| 步骤 | Agent / action | 状态 | 耗时 |
|---|---|---|---:|
| 1 | PlannerAgent / generate_learning_path | succeeded | 321 ms |
| 2 | ResourceAgent / generate_explanation | succeeded | 47,787 ms |
| 3 | QuizAgent / generate_quiz | succeeded | 529 ms |
| 4 | ReviewAgent / review_artifacts | succeeded | 164 ms |

高风险状态机与用户隔离真实数据库验收：

```text
task_id: 1ebd6cb9-d799-4f54-ac86-d8bf4964040c
status: waiting_confirmation → planned → cancelled
risk_level: high
requires_confirmation: true
其他学生查询: HTTP 404
```

## 浏览器验收

访问：

```text
http://127.0.0.1:3000/assistant?api_base=http://127.0.0.1:8010/api/v1&course_id=0b41dca8-3e7d-420b-9769-b4fe623e482f
```

实际结果：

1. 输入包含学习计划、讲解资料、练习题和课堂讲解的复杂请求后，页面生成结构化 `AgentTask · PERSONALIZED_LEARNING_PACKAGE` 卡片，没有退化为普通 Tutor 文本回答。
2. 卡片展示目标“补强图和排序”、low 风险、无需人工确认和 4 个待执行步骤。
3. 点击“开始执行”后，页面轮询并最终展示 4 个 succeeded 步骤。
4. 页面实际展示 `learning_path`、`resource`、`quiz`、`review_result` 四类 artifact。
5. 浏览器控制台无 error 或 warning。

## 工程检查

```text
python -m alembic upgrade head                          通过
python -m pytest                                       121 passed
python scripts/export_implementation_docs.py            通过，96 API / 30 tables
python scripts/check_docs.py                            通过
npm run typecheck                                      通过
npm run build                                          通过
浏览器 /assistant AgentTask 卡片、执行、时间线、产物     通过
```

## 结论与边界

Phase 2 和 Phase 3 已达到冲刺推进方案 Gate：

```text
复杂自然语言任务 → 结构化 AgentTask → 白名单计划
→ 分步骤真实执行 → Review → 多 artifact → 页面时间线
```

当前明确边界：

- 执行器为同步固定计划 MVP，不是开放式自治 Agent。
- 长任务仍使用轮询，不是后台队列或 SSE。
- HTML 课堂当前产出课堂讲解草稿资源，完整交互课堂属于 Phase 7。
- 对话式多轮画像访谈属于 Phase 4。
