# 12_Agent调度接口

> 文档状态：**当前实现事实源**
>
> 生成日期：2026-07-24
>
> 模块：Agent 调度与日志
>
> Router tag：`agents`
> HTTP 操作数：**4**

| 方法 | 路径 | 权限 | Path / Query 参数 | 请求体 |
|---|---|---|---|---|
| `GET` | `/api/v1/agents/ping` | JWT | - | - |
| `POST` | `/api/v1/agents/run` | JWT | - | application/json: `AgentRunRequest` |
| `GET` | `/api/v1/agents/runs` | JWT | task_type, status, page, page_size | - |
| `GET` | `/api/v1/agents/runs/{run_id}` | JWT | run_id* | - |

## 维护说明

请求与响应精确 Schema 以 `docs/assets/api/openapi-current.json` 和运行时 Swagger 为准。修改 Router 或 Schema 后执行：

```powershell
python scripts/export_implementation_docs.py
```
