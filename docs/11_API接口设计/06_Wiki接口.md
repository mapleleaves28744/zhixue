# 06_Wiki接口

> 文档状态：**当前实现事实源**
>
> 模块：LLM Wiki
>
> Router tag：`wiki`
> HTTP 操作数：**12**

| 方法 | 路径 | 权限 | Path / Query 参数 | 请求体 |
|---|---|---|---|---|
| `GET` | `/api/v1/wiki/graph` | JWT | course_id* | - |
| `GET` | `/api/v1/wiki/pages` | JWT | course_id*, status, page, page_size | - |
| `POST` | `/api/v1/wiki/pages` | JWT | - | application/json: `WikiPageCreate` |
| `POST` | `/api/v1/wiki/pages/generate-from-material` | JWT | - | application/json: `GenerateFromMaterialRequest` |
| `POST` | `/api/v1/wiki/pages/update-from-note` | JWT | - | application/json: `UpdateFromNoteRequest` |
| `GET` | `/api/v1/wiki/pages/{page_id}` | JWT | page_id* | - |
| `PUT` | `/api/v1/wiki/pages/{page_id}` | JWT | page_id* | application/json: `WikiPageUpdate` |
| `DELETE` | `/api/v1/wiki/pages/{page_id}` | JWT | page_id* | - |
| `POST` | `/api/v1/wiki/pages/{page_id}/rollback/{version_number}` | JWT | page_id*, version_number* | - |
| `POST` | `/api/v1/wiki/pages/{page_id}/summarize` | JWT | page_id* | - |
| `GET` | `/api/v1/wiki/pages/{page_id}/versions` | JWT | page_id* | - |
| `GET` | `/api/v1/wiki/pages/{page_id}/versions/{version_number}` | JWT | page_id*, version_number* | - |

## 维护说明

请求与响应精确 Schema 以 `docs/assets/api/openapi-current.json` 和运行时 Swagger 为准。修改 Router 或 Schema 后执行：

```powershell
python scripts/export_implementation_docs.py
```
