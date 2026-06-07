# Phase 3.1 LangGraph + MiMo 真正学习智能体阶段验收记录

> 验收日期：2026-06-07  
> 验收分支：`change_2`  
> 验收环境：本机 PostgreSQL、Redis 3.0.504、FastAPI、arq Worker、Next.js、真实 Xiaomi MiMo-V2.5。  
> 验收结论：**Phase 3.1 核心实现与真实浏览器主链路通过验收。**

## 验收范围

本次验收覆盖 MiMo 原生工具调用、LangGraph 动态规划/执行/观察/重规划闭环、集中 Tool Registry、风险中断、幂等执行、对话与事件持久化、PostgreSQL checkpoint、arq 后台任务、SSE、长期记忆反思和 Stitch `/assistant` 统一入口。

旧固定 `LearningTaskGraph` 保留为 `legacy_workflow` 回滚链路，不再是 `/assistant` 默认执行方式。

## 实际实现

- 新增 `backend/app/agent_runtime/`：`AgentState`、MiMo Supervisor、Tool Registry、Service tools 和 LangGraph `StateGraph`。
- 默认图节点：`load_context → supervisor → approval/execute_tool → observe → supervisor/replan → review → memory_reflect → finalize`。
- MiMo 调用继续经过统一 LLM Provider；真实 Agent 强制 `allow_mock_fallback=false`。
- Tool Registry 只调用 Service，声明输入 Schema、风险、超时、重试、写库和确认策略。
- `task_id + tool_call_id` 作为写库工具幂等键；任务恢复不会重复创建相同产物。
- 新增会话、消息、追加式事件、动态步骤与 LangGraph PostgreSQL checkpoint。
- Redis + arq Worker 执行后台任务；浏览器断开不影响 Worker 继续执行。
- `/assistant` 所有消息统一进入 Supervisor，自动执行并通过 SSE 展示计划、工具、观察、重规划、Review、记忆和最终结果。
- 页面不展示模型原始思维链，只展示简洁决策摘要。

## 数据库与 API

新增业务表：

```text
agent_conversations
agent_messages
agent_task_events
```

新增 LangGraph checkpoint 表：

```text
checkpoint_migrations
checkpoints
checkpoint_blobs
checkpoint_writes
```

新增统一 Agent API：

```text
POST /api/v1/agent/conversations
GET  /api/v1/agent/conversations
GET  /api/v1/agent/conversations/{conversation_id}/messages
POST /api/v1/agent/conversations/{conversation_id}/messages
GET  /api/v1/agent/tasks/{task_id}
GET  /api/v1/agent/tasks/{task_id}/events
POST /api/v1/agent/tasks/{task_id}/resume
POST /api/v1/agent/tasks/{task_id}/cancel
```

## 真实 MiMo 与浏览器验收

内置浏览器访问：

```text
http://127.0.0.1:3000/assistant
```

输入：

```text
请先检索课程知识库，再解释栈和队列的区别，最后给出两条复习建议。
```

真实结果：

| 指标 | 结果 |
|---|---:|
| task_id | `bdaa97b4-ac34-44c1-a809-b42202871027` |
| provider / model | `xiaomi_mimo / mimo-v2.5` |
| fallback_used | `false` |
| 最终状态 | `succeeded` |
| 规划/观察循环 | 2 |
| 工具调用 | 1 |
| 动态选择工具 | `KnowledgeAgent / search_course_knowledge` |
| 引用 | 10 条课程资料 |
| 事件 | queued、planning、plan_created、tool_started、tool_completed、observation、plan_created、reviewed、memory_reflected、completed |

页面实际展示：

1. 用户发送后自动入队，无“开始执行”按钮。
2. MiMo 动态生成“检索资料 → 解释区别 → 给出复习建议”计划。
3. 展示工具调用、观察、Review Agent、Memory Agent 和最终完成状态。
4. 最终回答绑定课程资料标题和检索分数。
5. 页面未展示原始思维链。

另一个真实 arq 后台任务 `86c70c60-8b59-4a57-95bc-b17d14738e43` 在浏览器之外完成，状态 `succeeded`，证明后台执行链路可用。

## 验收中发现并修复

1. 会话提交后直接序列化 `updated_at` 触发 SQLAlchemy `MissingGreenlet`。修复为提交后刷新 conversation/message/task。
2. MiMo 返回缺少必填参数的工具调用时，原实现直接终止任务。修复为生成失败 observation，让 Supervisor 可以重新规划。
3. 本机 Redis 3.0 不支持 Redis Stream。运行时自动兼容为 PostgreSQL 追加式事件作为事实源、Redis Pub/Sub 负责实时通知。

## 标准场景集

已建立：

```text
data/seed_knowledge/data_structure/eval/agent_runtime_scenarios.yml
scripts/evaluate_agent_runtime.py
```

场景集包含 20 条任务，覆盖 grounded QA、规划、资源、练习、诊断、推荐、画像、记忆、多 Agent、Review、高风险中断和非法工具拒绝。

真实 MiMo 批量评测结果：

| 指标 | 结果 | 目标 |
|---|---:|---:|
| 场景通过率 | 100%（20/20） | - |
| 任务完成率 | 95% | ≥ 85% |
| 工具选择准确率 | 100% | ≥ 90% |
| 可恢复故障重规划成功率 | 100% | ≥ 80% |
| 高风险操作拦截率 | 100% | 100% |
| 重复写入 | 0 | 0 |
| 跨用户数据泄露 | 0 | 0 |

任务完成率未计入停在 `waiting_confirmation` 的高风险任务，因此为 95%；该任务按设计通过高风险拦截验收。

多轮上下文真实样例：

```text
第一轮：解释栈和队列的区别，并给出两条复习建议。
第二轮：根据你刚才给出的两条复习建议，把第一条改成今天可以完成的三个具体动作。
```

第二轮在同一 conversation/thread 中成功引用第一轮建议，输出决策卡片、判断题和反向映射三个具体动作。

## 工程检查

```text
python -m alembic upgrade head                         通过
python -m pytest -q                                    143 passed
python scripts/export_implementation_docs.py           通过，104 API / 33 ORM tables
python scripts/check_docs.py                           通过
python scripts/evaluate_agent_runtime.py --validate-only 通过，20 scenarios
npm run typecheck                                      通过
npm run build                                          通过
内置浏览器 /assistant 真实 MiMo 动态任务               通过
```

执行方式：

```powershell
python scripts/evaluate_agent_runtime.py --validate-only
python scripts/evaluate_agent_runtime.py --user-id <user_id> --course-id <course_id>
```

## 边界与风险

- 当前 MiMo Token Plan 仅用于本地开发/比赛演示，正式部署必须切换为允许自定义后端使用的普通 MiMo API。
- 当前 Redis 3.0 使用 Pub/Sub 兼容模式；升级 Redis 5+ 后可启用 Redis Stream 的可重放实时事件。
- Agent 不允许自动修改源代码、数据库结构、权限或部署配置。
- Mock Provider 只用于自动化测试，不用于本次真实 Agent 效果验收。
