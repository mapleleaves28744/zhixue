# Task 4 Report: Atomic Claim, Short Transactions, and Tool Timing

## Status

Implemented and verified.

## Scope

Changed only the approved Task 4 runtime and test files:

- `backend/app/repositories/agent_task_repository.py`
- `backend/app/services/agent_runtime_service.py`
- `backend/app/agent_runtime/graph.py`
- `backend/tests/test_agent_cancellation.py`
- `backend/tests/test_agent_runtime.py`

No API, schema, model, migration, frontend, demo-data, real-provider acceptance, prompt, or structured-output files were changed.

## Delivered behavior

1. `AgentTaskRepository.claim_queued_task()` performs a conditional `UPDATE` limited to queued LangGraph tasks, setting `running`, `started_at`, and clearing the previous error.
2. `AgentRuntimeService.execute()` claims before loading the task, user, or conversation messages. A failed claim returns `{"status": "already_claimed"}` and does not execute the graph or write a failure state.
3. A successful claim is committed immediately. The read-only runtime context commits after it has loaded, before the graph can call the provider.
4. Runtime exceptions roll back the active session before `_mark_failed()` records the failure.
5. Graph tool execution is measured with `time.perf_counter()`. `tool_completed` events include non-negative integer `duration_ms`, and the matching `agent_task_steps.duration_ms` is updated during event persistence. `_save_tool_result()` also accepts a measured result duration when available.
6. Existing cancellation checks and checkpoint-based resume flow remain in place; resumed tasks are re-queued and use the same atomic claim path.

## TDD evidence

Added failing tests first for:

- competing executor skips Graph execution;
- runtime failure rolls back before failure recording;
- `tool_completed` carries `duration_ms`.

RED was observed with the prior code: the claim test attempted user loading, the rollback test saw zero rollbacks, and the timing test raised `KeyError: 'duration_ms'`.

## Verification

Fresh final command from `backend/`:

```bash
./.venv/bin/python -m pytest tests/test_agent_cancellation.py tests/test_agent_runtime.py -v
```

Result: `54 passed` in 2.43s. `git diff --check` also passed.

The test run emits only existing pytest-asyncio configuration and FastAPI lifespan deprecation warnings.

## Concerns

No implementation blockers. Full repository pytest was not run; verification was limited to the Task 4-required Agent Runtime suite.

## Review follow-up (2026-07-12)

Addressed all Task 4 review findings:

1. After task, user, message, provider, registry, and callback setup, the runtime now commits before entering either `graph.run()` or `graph.resume()`. The context-loader commit remains for the additional read transaction opened while loading profile and memory for a new run.
2. The post-claim `try` block now covers all setup and graph execution work. Any setup or runtime exception rolls back first, reloads the claimed task if needed, and records a failure so a successfully claimed task is not left `running`.
3. Cancellation returns retain their prior response and now roll back the local read transaction before returning.
4. Added review regression tests for the resume pre-call commit, setup-failure rollback/failure recording, matching-step duration persistence, and the repository's controlled conditional-update predicate.

Review RED evidence: the resume test observed only one commit before `graph.resume`, and user-load failure did not call `_mark_failed`.

Review GREEN verification:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_agent_cancellation.py tests/test_agent_runtime.py -v
```

Result: `58 passed` in 2.48s. `git diff --check` passed.
