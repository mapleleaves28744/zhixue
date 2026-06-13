# AnySearch Skill（智学工坊集成说明）

本目录 vendoring 自 [anysearch-ai/anysearch-skill](https://github.com/anysearch-ai/anysearch-skill)。

## 后端 Agent 集成

智学工坊 Agent 通过 `search_web` 工具调用 AnySearch，无需在对话链路中手动执行 CLI。

- 服务：`backend/app/services/web_search_service.py`
- 工具注册：`backend/app/agent_runtime/service_tools.py`
- 环境变量：`ANYSEARCH_API_KEY`（见项目根 `.env.example`）

## 本地 CLI 调试（可选）

```bash
export ANYSEARCH_API_KEY=your_key
python3 third_party/anysearch-skill/scripts/anysearch_cli.py search "hello world" --max_results 1
```

## Cursor Skill

若需在 Cursor 编辑器内直接使用 AnySearch，可将本目录链接到 `~/.cursor/skills/anysearch` 或项目 `.cursor/skills/anysearch`。
