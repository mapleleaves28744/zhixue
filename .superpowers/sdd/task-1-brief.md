### Task 1: 实现并接入按意图工具筛选

**Files:**
- Create: `backend/app/agent_runtime/tool_selector.py`
- Modify: `backend/app/agent_runtime/graph.py:150-202`
- Modify: `backend/tests/test_agent_runtime.py`

**Interfaces:**
- Produces: `select_tool_schemas(state: Mapping[str, Any], tool_schemas: Sequence[dict[str, Any]]) -> list[dict[str, Any]]`.
- Preserves: `Supervisor.decide(state, tool_schemas)`.

- [ ] **Step 1: Write failing tests**

```python
from app.agent_runtime.tool_selector import select_tool_schemas

def schema(name: str) -> dict[str, object]:
    return {"type": "function", "function": {"name": name, "parameters": {"type": "object"}}}

def test_course_qa_exposes_only_grounded_tools() -> None:
    tools = [schema(n) for n in ("search_course_knowledge", "answer_course_question", "generate_quiz")]
    selected = select_tool_schemas({"goal": "解释栈", "tool_hints": [], "skip_tools": []}, tools)
    assert [item["function"]["name"] for item in selected] == ["search_course_knowledge", "answer_course_question"]

def test_ppt_excludes_video_tool() -> None:
    tools = [schema(n) for n in ("search_course_knowledge", "generate_interactive_courseware", "generate_lesson_video")]
    selected = select_tool_schemas({"goal": "做一份二叉树 PPT", "tool_hints": [], "skip_tools": []}, tools)
    assert {item["function"]["name"] for item in selected} == {"search_course_knowledge", "generate_interactive_courseware"}
```

- [ ] **Step 2: Verify RED**

Run: `cd backend && python -m pytest tests/test_agent_runtime.py -k 'grounded_tools or excludes_video' -v`

Expected: `ModuleNotFoundError` for `tool_selector`.

- [ ] **Step 3: Implement minimal selector and Graph call**

```python
def select_tool_schemas(state, tool_schemas):
    available = {str(item.get("function", {}).get("name")): item for item in tool_schemas}
    goal = str(state.get("goal") or "")
    planned = supervisor_intents.plan_required_tools(
        goal,
        is_profile_update_only=supervisor_intents.is_profile_update_only_goal(goal),
    )
    names = _dedupe([*planned, *(state.get("tool_hints") or [])])
    skipped = set(state.get("skip_tools") or [])
    return [available[name] for name in names if name in available and name not in skipped] or list(tool_schemas)
```

In `_supervise`, pass the selected schemas to `decide()` and include `total_tool_count` and `candidate_tool_count` in the existing plan event payload.

- [ ] **Step 4: Verify GREEN and commit**

Run: `cd backend && python -m pytest tests/test_agent_runtime.py tests/test_supervisor_intents.py -v`

Commit: `git add backend/app/agent_runtime/tool_selector.py backend/app/agent_runtime/graph.py backend/tests/test_agent_runtime.py && git commit -m "feat: limit agent tools by intent"`

