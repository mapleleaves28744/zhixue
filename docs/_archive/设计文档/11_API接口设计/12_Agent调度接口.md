# 12_Agent调度接口

> 文档状态：**当前实现事实源**
>
> 生成日期：2026-10-12
>
> 模块：Agent 对话、任务、调度与日志
>
> Router tag：`agents`, `agent`, `agent-tasks`
> HTTP 操作数：**20**

| 方法 | 路径 | 权限 | Path / Query 参数 | 请求体 |
|---|---|---|---|---|
| `GET` | `/api/v1/agents/ping` | JWT | - | - |
| `POST` | `/api/v1/agents/run` | JWT | - | application/json: `AgentRunRequest` |
| `GET` | `/api/v1/agents/runs` | JWT | task_type, status, page, page_size | - |
| `GET` | `/api/v1/agents/runs/{run_id}` | JWT | run_id* | - |
| `GET` | `/api/v1/agent/conversations` | JWT | - | - |
| `POST` | `/api/v1/agent/conversations` | JWT | - | application/json: `AgentConversationCreateRequest` |
| `GET` | `/api/v1/agent/conversations/{conversation_id}/messages` | JWT | conversation_id*, limit | - |
| `POST` | `/api/v1/agent/conversations/{conversation_id}/messages` | JWT | conversation_id* | application/json: `AgentMessageCreateRequest` |
| `GET` | `/api/v1/agent/tasks/{task_id}` | JWT | task_id* | - |
| `POST` | `/api/v1/agent/tasks/{task_id}/cancel` | JWT | task_id* | - |
| `GET` | `/api/v1/agent/tasks/{task_id}/events` | JWT | task_id* | - |
| `GET` | `/api/v1/agent/tasks/{task_id}/events/history` | JWT | task_id* | - |
| `POST` | `/api/v1/agent/tasks/{task_id}/requeue` | JWT | task_id* | - |
| `POST` | `/api/v1/agent/tasks/{task_id}/resume` | JWT | task_id* | application/json: `AgentTaskResumeRequest` |
| `POST` | `/api/v1/agent-tasks/create` | JWT | - | application/json: `AgentTaskCreateRequest` |
| `GET` | `/api/v1/agent-tasks/{task_id}` | JWT | task_id* | - |
| `POST` | `/api/v1/agent-tasks/{task_id}/cancel` | JWT | task_id* | - |
| `POST` | `/api/v1/agent-tasks/{task_id}/confirm` | JWT | task_id* | - |
| `POST` | `/api/v1/agent-tasks/{task_id}/run` | JWT | task_id* | - |
| `GET` | `/api/v1/agent-tasks/{task_id}/steps` | JWT | task_id* | - |

## 维护说明

请求与响应精确 Schema 以 `docs/assets/api/openapi-current.json` 和运行时 Swagger 为准。修改 Router 或 Schema 后执行：

```powershell
python scripts/export_implementation_docs.py
```
