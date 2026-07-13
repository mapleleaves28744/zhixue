# Agent Runtime 收敛优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 限制 LLM 可见工具、拆分 Runtime 过载文件，并修复重复任务接管和长事务问题。

**Architecture:** 保留 `MiMoSupervisor` 与 `build_learning_tool_registry()` 的兼容入口。Graph 在每轮调用 Supervisor 前用 `ToolSelector` 缩小完整 Registry；ToolSet 和 Supervisor 内部职责拆为领域模块；Runtime 用条件更新接管 queued 任务。

**Tech Stack:** Python 3.12、SQLAlchemy AsyncSession、LangGraph、Pydantic、pytest。

## Global Constraints

- 不修改 API、Schema、Model、migration、学生端页面或演示数据。
- 保持既有 24 个工具的名称、JSON Schema、风险等级、确认要求和 handler 行为。
- 不改动已有的 `structured_outputs.py`、`prompt_service.py` 和真实 Provider 验收文件。
- 每项生产代码先有失败测试；无前端改动时不重做 UI。

---

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

### Task 2: 拆分领域 ToolSet，保持 Registry 契约

**Files:**
- Create: `backend/app/agent_runtime/toolsets/__init__.py`
- Create: `backend/app/agent_runtime/toolsets/common.py`
- Create: `backend/app/agent_runtime/toolsets/knowledge_tools.py`
- Create: `backend/app/agent_runtime/toolsets/learning_tools.py`
- Create: `backend/app/agent_runtime/toolsets/profile_tools.py`
- Create: `backend/app/agent_runtime/toolsets/review_tools.py`
- Create: `backend/app/agent_runtime/toolsets/media_tools.py`
- Modify: `backend/app/agent_runtime/service_tools.py`
- Modify: `backend/tests/test_agent_runtime.py`

**Interfaces:**
- Produces: `register_knowledge_tools`, `register_learning_tools`, `register_profile_tools`, `register_review_tools`, `register_media_tools`.
- Preserves: `build_learning_tool_registry(db, current_user, *, result_loader=None, result_saver=None)`.

- [ ] **Step 1: Write failing Registry-equivalence test**

```python
def test_learning_registry_keeps_public_tool_contracts() -> None:
    registry = build_learning_tool_registry(SimpleNamespace(), SimpleNamespace(id=uuid4()))
    schemas = {item["function"]["name"]: item["function"]["parameters"] for item in registry.tool_schemas()}
    assert set(schemas) == EXPECTED_TOOL_NAMES
    assert schemas["generate_interactive_courseware"]["required"] == ["topic"]
    assert registry.risk_level("apply_evolution_strategy") == "high"
    assert registry.requires_confirmation("apply_evolution_strategy") is True
```

Set `EXPECTED_TOOL_NAMES` to the current 24 tool names plus an assertion that each ToolSet module exports its registration function. This fails until ToolSet modules exist.

- [ ] **Step 2: Verify RED**

Run: `cd backend && python -m pytest tests/test_agent_runtime.py::test_learning_registry_keeps_public_tool_contracts -v`

Expected: import failure for `app.agent_runtime.toolsets`.

- [ ] **Step 3: Move handlers without altering registration**

```python
async def register_knowledge_tools(registry: ToolRegistry, db: AsyncSession, current_user: User) -> None:
    register_tool(registry, "search_course_knowledge", "使用向量、关键词、metadata 和 rerank 混合检索课程资料，返回可引用片段。", "KnowledgeAgent", {"query": {"type": "string"}, "top_k": {"type": "integer", "minimum": 1, "maximum": 20}}, ["query"], search_knowledge)
    register_tool(registry, "search_web", "通过 AnySearch 联网搜索互联网实时信息，返回可引用的网页标题、URL 与摘要。", "KnowledgeAgent", WEB_SEARCH_PROPERTIES, ["query"], search_web, timeout_seconds=45)
    register_tool(registry, "parse_uploaded_document", "解析已上传的课程资料（PDF/DOCX/TXT/MD），自动切片和向量化，供 RAG 检索使用。", "KnowledgeAgent", {"material_id": {"type": "string"}}, ["material_id"], parse_document, writes_db=True)
    register_tool(registry, "generate_mindmap", "围绕课程知识点生成 Mermaid 思维导图，可视化知识结构关系。", "KnowledgeAgent", MINDMAP_PROPERTIES, ["topic"], generate_mindmap_handler, writes_db=True)
    register_tool(registry, "generate_diagram", "围绕知识概念生成流程图、架构图或示意图的 Mermaid 代码。", "KnowledgeAgent", DIAGRAM_PROPERTIES, ["concept"], generate_diagram_handler, writes_db=True)
```

Move current nested handlers and `_register` calls verbatim: knowledge/search to `knowledge_tools`; path/explanation/quiz/diagnosis/recommendations to `learning_tools`; profile/memory/evolution to `profile_tools`; review handlers to `review_tools`; audio/image/video/courseware handlers to `media_tools`. Keep a shared `register_tool(...)` helper in `common.py`. `service_tools.py` constructs the Registry and invokes ToolSets in current registration order.

- [ ] **Step 4: Verify GREEN and commit**

Run: `cd backend && python -m pytest tests/test_agent_runtime.py tests/test_tool_registry_jsonschema.py -v`

Commit: `git add backend/app/agent_runtime/service_tools.py backend/app/agent_runtime/toolsets backend/tests/test_agent_runtime.py && git commit -m "refactor: split agent service toolsets"`

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

### Task 5: 完整验证与事实基线

**Files:**
- Modify: `docs/当前实现基线.md`

- [ ] **Step 1: Update baseline fact**

Add one factual Agent Runtime bullet: intent-scoped candidate tools, existing event/step timing, and atomic queued-task claim are implemented; no new database table or API is introduced.

- [ ] **Step 2: Run focused regression**

Run: `cd backend && python -m pytest tests/test_agent_runtime.py tests/test_supervisor_intents.py tests/test_agent_harness.py tests/test_agent_cancellation.py -v`

Expected: PASS.

- [ ] **Step 3: Run full verification**

Run: `cd backend && python -m pytest`

Expected: PASS. If unrelated dirty-worktree changes fail, report them without altering those files.

- [ ] **Step 4: Check docs and diff**

Run: `python scripts/check_docs.py && git diff --check`

Expected: exit code 0.

- [ ] **Step 5: Commit the verified baseline**

Commit: `git add docs/当前实现基线.md && git commit -m "docs: record agent runtime convergence"`
