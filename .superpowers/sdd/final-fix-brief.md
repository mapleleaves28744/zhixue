# Agent Runtime 最终审查修复

## 范围

修复最终审查确认的两项 Agent Runtime 缺口，不触碰本任务开始前已存在的用户改动（`structured_outputs.py`、`prompt_service.py`、`scripts/real_provider_acceptance.py`、`scripts/fast_deploy_code.sh` 及其相关文件）。

## 修复 1：候选工具执行边界

- `LearningAgentGraph` 将完整 Registry schema 交给 `ToolSelector`，Supervisor 只能看到候选 schema；此边界必须在执行前再次验证。
- `SupervisorPolicy.apply_safety_net` 必须丢弃或拒绝所有不在传入 `tool_schemas` 的 `decision.tool_calls`，即使该工具存在于完整 Registry。
- 若模型只返回被拒绝的非候选工具：不能成为 `pending_tool_calls`，应按现有安全网/交付物逻辑返回安全决策或失败，不得调用 Registry。
- 新增 TDD 回归：Provider 对“解释栈”返回注册但非候选的 `generate_quiz`，Graph 不得执行该 handler；正常候选 `answer_course_question`/检索行为不变。

## 修复 2：工具写库失败后的事务恢复

- `ToolRegistry` 仍应保持通用，不直接导入 SQLAlchemy 或数据库类型。
- 给 Registry 新增可选异步失败恢复回调，例如 `on_handler_error: Callable[[Exception], Awaitable[None]] | None`；其只在 handler 抛异常、且即将返回失败 `ToolExecutionResult` 前调用。
- `build_learning_tool_registry(db, ...)` 将该回调绑定为 `db.rollback`。回调自身失败仅记录日志，不遮蔽原 handler 错误。
- 这样 `_save_tool_result`/Runtime 事件持久化开始前会获得干净的 Session；保留现有重试和幂等行为。
- 新增 TDD 回归：模拟写库 handler 抛出异常，断言 rollback 回调已调用、结果仍为失败，并能通过 Runtime 保存失败 step（至少断言 `update_step(status="failed", ...)` 被调用）。

## 工具契约测试

- 扩展 Registry 契约测试，逐一断言 24 个工具的名称、agent_name、writes_db、risk_level、requires_confirmation、timeout_seconds 和 JSON schema 与当前既有契约一致；不要只断言名称集合和单个 courseware schema。

## 验证与边界

- 先写并运行失败测试，记录 RED；最小实现后运行 GREEN。
- 运行 `backend/.venv/bin/python -m pytest tests/test_agent_runtime.py tests/test_supervisor_intents.py tests/test_agent_harness.py tests/test_agent_cancellation.py tests/test_tool_registry_jsonschema.py -v`。
- 运行 `backend/.venv/bin/python -m pytest`、`backend/.venv/bin/python scripts/check_docs.py`、`git diff --check`。
- 仅提交本修复影响的 Agent Runtime 和测试文件；不暂存或修改任何既有用户改动。
- 报告写入 `.superpowers/sdd/final-fix-report.md`，包含 RED/GREEN 证据、测试输出、文件列表和未触碰的外部改动说明。
