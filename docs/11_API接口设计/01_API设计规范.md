# 01_API设计规范

> 文档状态：**当前实现规范**

## 基础约定

- 基础路径：`/api/v1`
- 认证：JWT Bearer Token
- 文件上传：`multipart/form-data`
- 分页默认参数：`page=1&page_size=20`
- 成功响应：`{"code": 0, "message": "success", "data": ..., "request_id": "..."}`
- 错误响应：包含 `code`、`message`、`detail`、`request_id`

## 权限事实源

权限校验以 `backend/app/core/deps.py`、各 Router 的依赖和 Service 的所有权校验为准。前端传入的 `user_id` 不可信；学生数据查询必须绑定当前 JWT 用户。

## 接口事实源

- 完整清单：`16_当前实现API清单.md`
- OpenAPI：`docs/assets/api/openapi-current.json`
- 运行时 Swagger：`http://127.0.0.1:8000/docs`
