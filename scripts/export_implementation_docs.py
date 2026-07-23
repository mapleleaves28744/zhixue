from __future__ import annotations

import json
import importlib
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DOCS = ROOT / "docs"
ARCHIVE_DESIGN = DOCS / "_archive" / "设计文档"
API_DIR = ARCHIVE_DESIGN / "11_API接口设计"
sys.path.insert(0, str(BACKEND))

from app.db.base import Base  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402

importlib.import_module("app.models")


HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
GENERATED_ON = date.today().isoformat()
PUBLIC_PATHS = {
    ("GET", "/"),
    ("GET", "/health"),
    ("GET", "/api/v1/ping"),
    ("GET", "/api/v1/auth/ping"),
    ("GET", "/api/v1/auth/check-username"),
    ("POST", "/api/v1/auth/register"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/reset-password"),
}

MODULES = [
    ("02_认证与用户接口.md", "认证与用户", ["auth", "users"]),
    ("03_课程空间接口.md", "课程空间", ["courses"]),
    ("04_资料上传与解析接口.md", "资料、知识抽取与检索", ["materials", "knowledge"]),
    ("05_智能问答接口.md", "AI Tutor", ["tutor"]),
    ("06_Wiki接口.md", "LLM Wiki", ["wiki"]),
    ("07_资源生成接口.md", "个性化资源", ["resources"]),
    ("08_题库练习接口.md", "练习与错题", ["quizzes"]),
    ("09_学习诊断接口.md", "诊断与推荐", ["diagnosis", "recommendations"]),
    ("10_学习路径推荐接口.md", "学习路径与学习记录", ["learning-paths", "learning-records"]),
    ("11_学生画像接口.md", "学生画像与长期记忆", ["student-profile", "student-memory"]),
    ("12_Agent调度接口.md", "Agent 调度与日志", ["agents"]),
    ("13_自进化策略接口.md", "自进化策略", ["evolution"]),
]


def write_markdown(path: Path, content: str) -> None:
    cleaned = "\n".join(line.rstrip() for line in content.splitlines()).rstrip() + "\n"
    path.write_text(cleaned, encoding="utf-8")


def schema_name(value: dict[str, Any] | None) -> str:
    if not value:
        return "-"
    ref = value.get("$ref")
    if ref:
        return ref.rsplit("/", 1)[-1]
    if value.get("type") == "array":
        return f"array[{schema_name(value.get('items'))}]"
    return str(value.get("type") or "object")


def request_schema(operation: dict[str, Any]) -> str:
    body = operation.get("requestBody", {}).get("content", {})
    for content_type in ("application/json", "multipart/form-data"):
        if content_type in body:
            name = schema_name(body[content_type].get("schema"))
            return f"{content_type}: `{name}`"
    return "-"


def response_schema(operation: dict[str, Any]) -> str:
    responses = operation.get("responses", {})
    success = responses.get("200") or responses.get("201") or {}
    content = success.get("content", {}).get("application/json", {})
    return f"`{schema_name(content.get('schema'))}`" if content else "统一响应"


def parameters(operation: dict[str, Any]) -> str:
    items = []
    for parameter in operation.get("parameters", []):
        required = "*" if parameter.get("required") else ""
        items.append(f"{parameter.get('name')}{required}")
    return ", ".join(items) or "-"


def endpoint_rows(spec: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(spec["paths"]):
        for method, operation in spec["paths"][path].items():
            if method.lower() not in HTTP_METHODS:
                continue
            upper_method = method.upper()
            rows.append(
                {
                    "method": upper_method,
                    "path": path,
                    "tags": operation.get("tags", []),
                    "summary": operation.get("summary") or operation.get("operationId") or "-",
                    "parameters": parameters(operation),
                    "request": request_schema(operation),
                    "response": response_schema(operation),
                    "permission": "Public" if (upper_method, path) in PUBLIC_PATHS else "JWT",
                }
            )
    return rows


def endpoint_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| 方法 | 路径 | 权限 | Path / Query 参数 | 请求体 |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['method']}` | `{row['path']}` | {row['permission']} | "
            f"{row['parameters']} | {row['request']} |"
        )
    return "\n".join(lines)


def write_api_docs(spec: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    api_dir = API_DIR
    assets_dir = DOCS / "assets" / "api"
    api_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    (assets_dir / "openapi-current.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for tag in row["tags"] or ["untagged"]:
            grouped[tag].append(row)

    overview = f"""# 11_API接口设计

## 目录导读

> 本文是当前 API 文档入口，由 FastAPI OpenAPI 自动生成。模块级接口摘要和完整清单保留为独立事实文档；未出现在 OpenAPI 中的旧设计接口均视为未实现。

- 当前模块与接口数量：见“当前模块”。
- 精确端点清单：`docs/当前实现API清单.md`（本目录 `16_当前实现API清单.md` 同步副本）。
- 请求和响应 Schema：`docs/assets/api/openapi-current.json` 或运行时 Swagger。
- 文档重新生成：`python scripts/export_implementation_docs.py`。

> 文档状态：**当前实现事实源**
>
> 生成方式：`python scripts/export_implementation_docs.py`
>
> 生成依据：FastAPI `app.openapi()`，共 **{len(rows)}** 个 HTTP 操作。
> 最后同步：{GENERATED_ON}

## 使用规则

1. 判断接口是否存在、方法和路径是否正确时，以 `docs/当前实现API清单.md`、`docs/assets/api/openapi-current.json` 和本目录模块文档为准。
2. 早期 PRD、设计方案中的接口若未出现在当前清单中，均视为“规划中或未实现”，不得直接调用。
3. 所有业务接口位于 `/api/v1`，成功响应统一包含 `code`、`message`、`data`、`request_id`。
4. 除清单中标记为 Public 的接口外，均要求 JWT Bearer Token。
5. Swagger 运行时入口：`http://127.0.0.1:8000/docs`。

## 当前模块

| 模块 | Tag | HTTP 操作数 | 详细文档 |
|---|---|---:|---|
"""
    for filename, title, tags in MODULES:
        count = sum(len(grouped[tag]) for tag in tags)
        overview += f"| {title} | {', '.join(f'`{tag}`' for tag in tags)} | {count} | `{filename}` |\n"
    overview += "\n"
    overview += """## 当前明确未实现

- `/api/v1/admin/*` 管理员后台业务接口。
- `/api/v1/auth/refresh`、`/api/v1/auth/logout`。
- 独立聊天会话与聊天历史列表接口。
- WebSocket 资料处理进度接口。
- 教师端业务接口。

## OpenAPI 快照

- JSON：`docs/assets/api/openapi-current.json`
- 完整端点表：`docs/当前实现API清单.md`
- 重新生成：`python scripts/export_implementation_docs.py`
"""
    write_markdown(api_dir / "11_API接口设计.md", overview)

    full = f"""# 当前实现 API 清单

> 文档状态：**自动生成的当前实现事实源**
>
> 生成日期：{GENERATED_ON}
>
> HTTP 操作数：**{len(rows)}**
> 生成命令：`python scripts/export_implementation_docs.py`

{endpoint_table(rows)}
"""
    write_markdown(DOCS / "当前实现API清单.md", full)
    write_markdown(api_dir / "16_当前实现API清单.md", full)

    design_spec = """# 01_API设计规范

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

- 完整清单：`docs/当前实现API清单.md`
- OpenAPI：`docs/assets/api/openapi-current.json`
- 运行时 Swagger：`http://127.0.0.1:8000/docs`
"""
    write_markdown(api_dir / "01_API设计规范.md", design_spec)

    for filename, title, tags in MODULES:
        module_rows = []
        for tag in tags:
            module_rows.extend(grouped[tag])
        content = f"""# {filename.removesuffix('.md')}

> 文档状态：**当前实现事实源**
>
> 生成日期：{GENERATED_ON}
>
> 模块：{title}
>
> Router tag：{', '.join(f'`{tag}`' for tag in tags)}
> HTTP 操作数：**{len(module_rows)}**

{endpoint_table(module_rows)}

## 维护说明

请求与响应精确 Schema 以 `docs/assets/api/openapi-current.json` 和运行时 Swagger 为准。修改 Router 或 Schema 后执行：

```powershell
python scripts/export_implementation_docs.py
```
"""
        write_markdown(api_dir / filename, content)

    admin = """# 14_管理员后台接口

> 文档状态：**范围冻结，当前未实现**

当前代码未注册 `/api/v1/admin/*` Router，也没有管理员后台业务页面。已有 `admin` 角色仅用于少量现有接口的权限分支，不代表管理员后台已经完成。

后续若恢复管理员专项，必须先更新 PRD、任务范围、权限测试和本文件，再实现接口。
"""
    write_markdown(api_dir / "14_管理员后台接口.md", admin)

    openapi_doc = """# 15_OpenAPI规范文件说明

> 文档状态：**当前实现**

FastAPI 是 OpenAPI 的唯一生成源。不要手工维护另一份 YAML 接口定义。

## 文件与入口

- 版本化快照：`docs/assets/api/openapi-current.json`
- 人工阅读清单：`docs/当前实现API清单.md`
- 运行时 Swagger：`http://127.0.0.1:8000/docs`

## 更新命令

```powershell
python scripts/export_implementation_docs.py
```

提交 API 变更前必须重新生成快照并检查对应模块文档。
"""
    write_markdown(api_dir / "15_OpenAPI规范文件说明.md", openapi_doc)


def write_database_docs() -> None:
    tables = sorted(Base.metadata.tables.values(), key=lambda table: table.name)
    lines = [
        "# 当前实现数据库清单",
        "",
        "> 文档状态：**自动生成的当前实现事实源**  ",
        f"> 生成日期：{GENERATED_ON}  ",
        "> 生成依据：SQLAlchemy `Base.metadata`  ",
        f"> 当前 ORM 表数量：**{len(tables)}**",
        "",
        "判断表、字段和外键是否存在时，以 Alembic migration、SQLAlchemy Model 和本清单为准；早期数据库设计文档用于解释设计意图。",
        "",
    ]
    for table in tables:
        lines.extend(
            [
                f"## `{table.name}`",
                "",
                "| 字段 | 类型 | 可空 | 主键 | 外键 |",
                "|---|---|---|---|---|",
            ]
        )
        for column in table.columns:
            foreign_keys = ", ".join(sorted(str(key.target_fullname) for key in column.foreign_keys)) or "-"
            lines.append(
                f"| `{column.name}` | `{column.type}` | {'是' if column.nullable else '否'} | "
                f"{'是' if column.primary_key else '否'} | `{foreign_keys}` |"
            )
        lines.append("")
    content = "\n".join(lines)
    write_markdown(DOCS / "当前实现数据库清单.md", content)
    write_markdown(ARCHIVE_DESIGN / "10_数据库设计" / "15_当前实现数据库清单.md", content)


def main() -> None:
    spec = fastapi_app.openapi()
    rows = endpoint_rows(spec)
    write_api_docs(spec, rows)
    write_database_docs()
    print(f"exported {len(rows)} API operations and {len(Base.metadata.tables)} database tables")


if __name__ == "__main__":
    main()
