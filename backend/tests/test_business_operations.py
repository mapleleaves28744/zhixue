from uuid import uuid4
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.agent_runtime.graph import LearningAgentGraph
from app.agent_runtime.tools import AgentTool, ToolRegistry, ToolExecutionResult
from app.agent_runtime.operation_identity import operation_key
from app.services.agent_runtime_service import AgentRuntimeService


@pytest.mark.asyncio
async def test_replanning_with_new_tool_call_id_reuses_business_artifact():
    persisted = {}
    writes = []
    async def load(key): return persisted.get(key)
    async def save(key, result): persisted[key] = result
    async def handler(context, arguments):
        writes.append(arguments["topic"])
        return ToolExecutionResult(output={"id": "quiz-1"}, artifact_refs=[{"type": "quiz", "id": "quiz-1"}])
    registry = ToolRegistry(result_loader=load, result_saver=save)
    registry.register(AgentTool(name="generate_quiz", description="quiz", agent_name="QuizAgent",
        input_schema={"type": "object"}, handler=handler, writes_db=True))
    graph = LearningAgentGraph.__new__(LearningAgentGraph)
    graph.registry, graph.event_sink = registry, AsyncMock()
    state = {"task_id": str(uuid4()), "conversation_id": str(uuid4()), "user_id": str(uuid4()),
             "course_id": str(uuid4()), "pending_tool_calls": [{"id": "first", "name": "generate_quiz", "arguments": {"topic": "栈"}}],
             "intent_frame_v1": {"revision": 1, "tasks": [{"id": "s1", "topic": "栈", "tools": ["generate_quiz"]}]}}
    first = await graph._execute_tool(state)
    registry._results.clear()  # Exercise durable recovery, not just the process cache.
    state["pending_tool_calls"][0]["id"] = "replanned"
    state["tool_calls"] = first["tool_calls"]
    second = await graph._execute_tool(state)
    assert writes == ["栈"]
    assert second["last_tool_result"]["artifact_refs"] == first["last_tool_result"]["artifact_refs"]


@pytest.mark.asyncio
async def test_unknown_committed_outcome_is_not_blindly_reexecuted():
    service = AgentRuntimeService(SimpleNamespace())
    service.tasks.get_step_by_operation = AsyncMock(return_value=SimpleNamespace(status="running"))
    result = await service._load_tool_result(f"{uuid4()}:op:r1:s1:generate_quiz")
    assert result.success is False and "结果未知" in result.error_message


def test_contract_revision_and_distinct_topics_have_distinct_operations():
    frame = {"revision": 1, "tasks": [{"id": "s1", "topic": "栈", "tools": ["generate_quiz"]},
                                     {"id": "s2", "topic": "队列", "tools": ["generate_quiz"]}]}
    state = {"intent_frame_v1": frame}
    first = operation_key(state, "generate_quiz", {"topic": "栈"})
    assert operation_key(state, "generate_quiz", {"topic": "队列"}) != first
    frame["revision"] = 2
    assert operation_key(state, "generate_quiz", {"topic": "栈"}) != first
