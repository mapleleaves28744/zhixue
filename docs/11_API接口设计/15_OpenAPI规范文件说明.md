# 15_OpenAPI规范文件说明

> 文档状态：**当前实现**

FastAPI 是 OpenAPI 的唯一生成源。不要手工维护另一份 YAML 接口定义。

## 文件与入口

- 版本化快照：`docs/assets/api/openapi-current.json`
- 人工阅读清单：`docs/11_API接口设计/16_当前实现API清单.md`
- 运行时 Swagger：`http://127.0.0.1:8000/docs`

## 更新命令

```powershell
python scripts/export_implementation_docs.py
```

提交 API 变更前必须重新生成快照并检查对应模块文档。
