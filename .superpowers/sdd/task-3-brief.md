### Task 3: 拆分 Supervisor 的策略、Prompt 和 Completion

**Files:**
- Create: `backend/app/agent_runtime/supervisor_policy.py`
- Create: `backend/app/agent_runtime/supervisor_prompt.py`
- Create: `backend/app/agent_runtime/supervisor_completion.py`
- Modify: `backend/app/agent_runtime/supervisor.py`
- Modify: `backend/app/agent_runtime/graph.py`
- Modify: `backend/tests/test_supervisor_intents.py`
- Modify: `backend/tests/test_agent_harness.py`

**Interfaces:**
- Produces: `apply_safety_net(...)`, `build_messages(...)`, `format_search_output_answer(...)`.
- Preserves: `MiMoSupervisor.decide(...)` and thin private wrappers used by current tests.

- [ ] **Step 1: Write failing completion/observability tests**

```python
def test_completion_formats_empty_course_search() -> None:
    answer = format_search_output_answer("search_course_knowledge", {"items": []}, "栈")
    assert "未找到相关结果" in answer

@pytest.mark.asyncio
async def test_plan_event_reports_selected_tool_count() -> None:
    events = []
    graph = make_graph_with_three_tools(events)
    await graph.run(
        task_id=uuid4(), conversation_id=uuid4(), user_id=uuid4(), course_id=uuid4(),
        goal="解释栈", thread_id="selected-tool-count",
    )
    payload = next(payload for kind, payload in events if kind == "plan_created")
    assert payload["total_tool_count"] == 3
    assert payload["candidate_tool_count"] == 2
```

- [ ] **Step 2: Verify RED**

Run: `cd backend && python -m pytest tests/test_supervisor_intents.py tests/test_agent_harness.py -k 'empty_course_search or selected_tool_count' -v`

Expected: import or missing payload assertion failure.

- [ ] **Step 3: Extract behavior verbatim**

Move the safety net, fallback, deliverable alignment and safe-argument code to policy; move system/context message construction to prompt; move search and artifact completion formatting to completion. Delegate from `MiMoSupervisor` and leave private forwarding methods for test compatibility. Measure `decide()` using `time.perf_counter()` and add `supervisor_duration_ms` to the plan event.

- [ ] **Step 4: Verify GREEN and commit**

Run: `cd backend && python -m pytest tests/test_supervisor_intents.py tests/test_agent_harness.py tests/test_agent_runtime.py -v`

Commit: `git add backend/app/agent_runtime/supervisor.py backend/app/agent_runtime/supervisor_policy.py backend/app/agent_runtime/supervisor_prompt.py backend/app/agent_runtime/supervisor_completion.py backend/app/agent_runtime/graph.py backend/tests/test_supervisor_intents.py backend/tests/test_agent_harness.py && git commit -m "refactor: separate supervisor responsibilities"`

