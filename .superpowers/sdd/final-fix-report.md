# Agent Runtime 最终审查修复报告

日期：2026-07-12

## 修复范围

1. Supervisor 安全网现在只保留当前候选 schema 中允许的工具调用。模型即使返回完整 Registry 中已注册、但未被候选集暴露的工具，也不会进入 `pending_tool_calls` 或执行 handler。
2. `ToolRegistry` 增加可选异步 `on_handler_error` 恢复回调。写库 handler 在重试耗尽后失败时，会在保存失败 step 前调用该回调；学习工具 Registry 将它绑定到 `db.rollback`。恢复回调自己的异常仅写日志，不覆盖原始 handler 错误。
3. Registry 契约测试现在逐一锁定 24 个工具的名称、Agent、写库标记、风险等级、确认要求、超时和完整 JSON Schema。

## TDD 证据

### RED

执行：

```text
backend/.venv/bin/python -m pytest tests/test_agent_runtime.py -k 'non_candidate_tool_call or failed_database_tool' -v
```

结果：2 failed。

- `test_non_candidate_tool_call_is_not_executed_from_full_registry`：失败于 `executed_quiz is False`，证明模型返回的非候选 `generate_quiz` 会错误穿透到完整 Registry 并执行。
- `test_failed_database_tool_rolls_back_before_runtime_saves_failed_step`：失败于 `db.rollback.assert_awaited_once()`，证明 handler 写库失败后没有恢复事务。

### GREEN

同一条命令在最小实现后结果：2 passed。

## 变更文件

- `backend/app/agent_runtime/supervisor_policy.py`
- `backend/app/agent_runtime/tools.py`
- `backend/app/agent_runtime/service_tools.py`
- `backend/tests/test_agent_runtime.py`

## 验证结果

```text
backend/.venv/bin/python -m pytest tests/test_agent_runtime.py tests/test_supervisor_intents.py tests/test_agent_harness.py tests/test_agent_cancellation.py tests/test_tool_registry_jsonschema.py -v
108 passed, 6 warnings

backend/.venv/bin/python -m pytest
466 passed, 6 warnings

backend/.venv/bin/python scripts/check_docs.py
documentation check passed: 4 active folders, 124 markdown files, no placeholders or broken local references

git diff --check
passed (no output)
```

pytest 警告均为已有 `pytest-asyncio` 默认 loop scope 和 FastAPI `on_event` 弃用提示；无测试失败。

## 未触碰的外部改动

未修改、未暂存或纳入本修复的既有内容包括：

- `backend/app/agents/structured_outputs.py`
- `backend/app/services/prompt_service.py`
- `scripts/real_provider_acceptance.py`
- `scripts/fast_deploy_code.sh`
- 既有真实 Provider 测试、计划/规格及任务证据以外的文档
- 预先存在的未跟踪 `.superpowers/` 内容与 `docs/superpowers/plans/2026-07-12-agent-runtime-convergence.md`

## 数据库与 API

- 数据库变更：无。
- API 变更：无。

## 风险与说明

- 无真实 LLM API Key 依赖；新增回归均使用本地 Provider/handler stub。
- 对空候选 schema 的旧测试已改为传入明确候选 schema，保证它们继续覆盖正常候选工具的结构化解析与安全参数补全路径。
- 恢复回调在 handler 重试耗尽后调用一次，保留既有重试与幂等结果缓存行为。

---

## 最终审查追加修复（2026-07-12）

### 问题与修复

审查发现：当 Provider 的所有工具调用都因不在候选 schema 中被拒绝、且没有待交付物时，安全网会错误直接返回 `complete`。

现已改为：

1. 仅当所有被过滤的调用确实都属于非候选工具时，进入该恢复分支；已完成或显式跳过的调用仍保留原有完成逻辑。
2. 依次优先使用允许的 `tool_hints`、计划 fallback，或当前候选 schema 中第一个未完成且未跳过的工具。
3. 没有任何安全候选时，返回明确的 `replan` 决策，拒绝执行非候选工具。

回归测试将“解释栈”的首轮 Provider 响应设为幻觉 `generate_quiz`：验证 Quiz handler 不执行，安全网改为执行候选 `search_course_knowledge`，第二轮正常完成，因此不会绕过候选路径直接完成。

### RED / GREEN 证据

```text
RED:
backend/.venv/bin/python -m pytest tests/test_agent_runtime.py -k non_candidate_tool_call -v
1 failed: expected safe search path, but no candidate handler executed.

GREEN:
同一命令
1 passed
```

### 验证

```text
backend/.venv/bin/python -m pytest tests/test_agent_runtime.py tests/test_supervisor_intents.py tests/test_agent_harness.py tests/test_agent_cancellation.py tests/test_tool_registry_jsonschema.py -v
108 passed, 6 warnings

backend/.venv/bin/python -m pytest
466 passed, 6 warnings
```

同时将 `docs/当前实现基线.md` 的后端 pytest 事实计数由 `442 passed` 更正为已验证的 `466 passed`；未改动其他基线陈述。

```text
backend/.venv/bin/python scripts/check_docs.py
documentation check passed: 4 active folders, 124 markdown files, no placeholders or broken local references

git diff --check
passed (no output)
```
