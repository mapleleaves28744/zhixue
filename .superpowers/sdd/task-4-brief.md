### Task 4: 原子接管、短事务和工具耗时

**Files:**
- Modify: `backend/app/repositories/agent_task_repository.py`
- Modify: `backend/app/services/agent_runtime_service.py`
- Modify: `backend/app/agent_runtime/graph.py`
- Modify: `backend/tests/test_agent_cancellation.py`
- Modify: `backend/tests/test_agent_runtime.py`

**Interfaces:**
- Produces: `claim_queued_task(task_id: UUID, started_at: datetime) -> bool`.
- Produces: `execute()` returning `{"status": "already_claimed"}` for competing executors.

- [ ] **Step 1: Write failing claim and duration tests**

```python
@pytest.mark.asyncio
async def test_execute_skips_graph_when_claim_is_owned(monkeypatch) -> None:
    service, task = build_runtime_service_for_claim(False)
    graph_run = AsyncMock()
    monkeypatch.setattr(LearningAgentGraph, "run", graph_run)
    assert await service.execute(task.id) == {"status": "already_claimed"}
    graph_run.assert_not_awaited()

@pytest.mark.asyncio
async def test_tool_completed_event_has_duration_ms() -> None:
    events = []
    await make_graph_with_one_tool(events).run(
        task_id=uuid4(), conversation_id=uuid4(), user_id=uuid4(), course_id=uuid4(),
        goal="解释栈", thread_id="tool-duration",
    )
    payload = next(payload for kind, payload in events if kind == "tool_completed")
    assert isinstance(payload["duration_ms"], int)
    assert payload["duration_ms"] >= 0
```

- [ ] **Step 2: Verify RED**

Run: `cd backend && python -m pytest tests/test_agent_cancellation.py tests/test_agent_runtime.py -k 'claim_is_owned or duration_ms' -v`

Expected: failure because claim API and duration payload are absent.

- [ ] **Step 3: Implement minimal guarded execution**

```python
result = await self.db.execute(
    update(AgentTask)
    .where(AgentTask.id == task_id, AgentTask.status == "queued", AgentTask.runtime_mode == "langgraph")
    .values(status="running", started_at=started_at, error_message=None)
)
return result.rowcount == 1
```

Claim before task/user/message loads; commit only after a successful claim. On false, return `already_claimed` without writing a failure. Commit after read-only context load before the first provider wait. On runtime exception roll back before `_mark_failed`. Measure tool Registry execution with `perf_counter`; include `duration_ms` in `tool_completed`, and persist it to the existing step column in `_save_tool_result`.

- [ ] **Step 4: Verify GREEN and commit**

Run: `cd backend && python -m pytest tests/test_agent_cancellation.py tests/test_agent_runtime.py -v`

Commit: `git add backend/app/repositories/agent_task_repository.py backend/app/services/agent_runtime_service.py backend/app/agent_runtime/graph.py backend/tests/test_agent_cancellation.py backend/tests/test_agent_runtime.py && git commit -m "fix: atomically claim and observe agent tasks"`

