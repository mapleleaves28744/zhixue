from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agent_runtime.graph import LearningAgentGraph
from app.agent_runtime.service_tools import build_learning_tool_registry
from app.agent_runtime.state import AgentDecision, PlannedToolCall
from app.agent_runtime.supervisor import MiMoSupervisor
from app.agent_runtime.tools import (
    AgentTool,
    ToolContext,
    ToolExecutionResult,
    ToolRegistry,
)
from app.llm.schemas import ChatResponse, ToolCall
from app.models.agent_conversation import AgentConversation, AgentMessage, AgentTaskEvent
from app.models.agent_task import AgentTask, AgentTaskStep
from app.services.agent_queue_service import AgentEventBroker


class QueryInput(SimpleNamespace):
    pass


@pytest.mark.asyncio
async def test_tool_registry_retries_and_reuses_idempotent_result() -> None:
    attempts = 0

    async def flaky_handler(context: ToolContext, arguments: dict[str, object]) -> ToolExecutionResult:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary failure")
        return ToolExecutionResult(
            output={"query": arguments["query"]},
            evidence=["course chunk"],
        )

    registry = ToolRegistry()
    registry.register(
        AgentTool(
            name="search_course_knowledge",
            description="检索课程知识库",
            agent_name="KnowledgeAgent",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            handler=flaky_handler,
            max_retries=2,
        )
    )
    context = ToolContext(
        task_id=uuid4(),
        tool_call_id="call_1",
        user_id=uuid4(),
        course_id=uuid4(),
    )

    first = await registry.execute("search_course_knowledge", {"query": "栈"}, context)
    second = await registry.execute("search_course_knowledge", {"query": "栈"}, context)

    assert first.output == {"query": "栈"}
    assert second.output == first.output
    assert attempts == 2


@pytest.mark.asyncio
async def test_tool_registry_reuses_persisted_result_after_process_restart() -> None:
    saved: dict[str, ToolExecutionResult] = {
        "persisted-key": ToolExecutionResult(output={"title": "已有资源"})
    }
    called = False

    async def handler(context: ToolContext, arguments: dict[str, object]) -> ToolExecutionResult:
        nonlocal called
        called = True
        return ToolExecutionResult(output={"title": "重复资源"})

    async def load_result(key: str) -> ToolExecutionResult | None:
        return saved.get(key)

    registry = ToolRegistry(result_loader=load_result)
    registry.register(
        AgentTool(
            name="generate_explanation",
            description="生成讲解",
            agent_name="ResourceAgent",
            input_schema={"type": "object", "properties": {}},
            handler=handler,
            writes_db=True,
        )
    )
    context = ToolContext(
        task_id=uuid4(),
        tool_call_id="call_1",
        user_id=uuid4(),
        course_id=uuid4(),
        idempotency_key_override="persisted-key",
    )

    result = await registry.execute("generate_explanation", {}, context)

    assert result.output["title"] == "已有资源"
    assert called is False


@pytest.mark.asyncio
async def test_tool_registry_rejects_unknown_and_high_risk_tools() -> None:
    async def handler(context: ToolContext, arguments: dict[str, object]) -> ToolExecutionResult:
        return ToolExecutionResult(output={"ok": True})

    registry = ToolRegistry()
    registry.register(
        AgentTool(
            name="apply_evolution_strategy",
            description="应用自进化策略",
            agent_name="EvolutionAgent",
            input_schema={"type": "object", "properties": {}},
            handler=handler,
            risk_level="high",
            requires_confirmation=True,
        )
    )
    context = ToolContext(
        task_id=uuid4(),
        tool_call_id="call_2",
        user_id=uuid4(),
        course_id=uuid4(),
    )

    with pytest.raises(ValueError, match="未知工具"):
        await registry.execute("run_shell", {}, context)
    assert registry.requires_confirmation("apply_evolution_strategy") is True


class SequencedSupervisor:
    def __init__(self) -> None:
        self.calls = 0

    async def decide(self, state, tool_schemas):
        self.calls += 1
        if self.calls == 1:
            return AgentDecision(
                status="continue",
                summary="先尝试检索",
                plan=["检索课程知识库", "生成解释"],
                tool_calls=[
                    PlannedToolCall(
                        id="search_1",
                        name="search_course_knowledge",
                        arguments={"query": "栈"},
                    )
                ],
            )
        if self.calls == 2:
            assert state["observations"][-1]["success"] is False
            return AgentDecision(
                status="continue",
                summary="检索失败，重新规划为生成解释",
                plan=["生成解释"],
                tool_calls=[
                    PlannedToolCall(
                        id="resource_1",
                        name="generate_explanation",
                        arguments={"topic": "栈"},
                    )
                ],
            )
        return AgentDecision(
            status="complete",
            summary="任务完成",
            final_answer="已根据重新规划生成栈的讲解。",
        )


@pytest.mark.asyncio
async def test_langgraph_agent_observes_failure_and_replans_dynamically() -> None:
    async def failed_search(context: ToolContext, arguments: dict[str, object]) -> ToolExecutionResult:
        raise RuntimeError("retrieval unavailable")

    async def generate_resource(context: ToolContext, arguments: dict[str, object]) -> ToolExecutionResult:
        return ToolExecutionResult(
            output={"title": "栈讲解"},
            artifact_refs=[{"type": "resource", "id": "resource-1", "title": "栈讲解"}],
        )

    registry = ToolRegistry()
    registry.register(
        AgentTool(
            name="search_course_knowledge",
            description="检索课程知识库",
            agent_name="KnowledgeAgent",
            input_schema={"type": "object", "properties": {}},
            handler=failed_search,
            max_retries=0,
        )
    )
    registry.register(
        AgentTool(
            name="generate_explanation",
            description="生成讲解",
            agent_name="ResourceAgent",
            input_schema={"type": "object", "properties": {}},
            handler=generate_resource,
        )
    )
    graph = LearningAgentGraph(registry=registry, supervisor=SequencedSupervisor())

    result = await graph.run(
        task_id=uuid4(),
        conversation_id=uuid4(),
        user_id=uuid4(),
        course_id=uuid4(),
        goal="帮我补强栈",
        thread_id="thread-replan",
    )

    assert result["status"] == "completed"
    assert result["final_answer"] == "已根据重新规划生成栈的讲解。"
    assert result["replan_count"] >= 1
    assert [item["tool_name"] for item in result["observations"]] == [
        "search_course_knowledge",
        "generate_explanation",
    ]
    assert result["artifacts"][0]["type"] == "resource"


class FakeProvider:
    async def chat(self, messages, **kwargs):
        return ChatResponse(
            content="",
            finish_reason="tool_calls",
            reasoning_content="protocol-state",
            tool_calls=[
                ToolCall(
                    id="call_native",
                    name="search_course_knowledge",
                    arguments={"query": "二叉树"},
                )
            ],
        )


@pytest.mark.asyncio
async def test_mimo_supervisor_prefers_native_tool_calls() -> None:
    supervisor = MiMoSupervisor(provider=FakeProvider())

    decision = await supervisor.decide(
        {
            "goal": "解释二叉树",
            "messages": [{"role": "user", "content": "解释二叉树"}],
            "observations": [],
            "artifacts": [],
            "iteration_count": 0,
        },
        [
            {
                "type": "function",
                "function": {
                    "name": "search_course_knowledge",
                    "description": "检索",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
    )

    assert decision.status == "continue"
    assert decision.tool_calls[0].name == "search_course_knowledge"
    assert decision.reasoning_content == "protocol-state"


class StructuredDecisionProvider:
    async def chat(self, messages, **kwargs):
        return ChatResponse(
            content=(
                '{"thoughts":"private","decision":"先检索课程资料",'
                '"tool_calls":[{"tool_name":"search_course_knowledge",'
                '"parameters":{"query":"栈","top_k":5}}]}'
            )
        )


@pytest.mark.asyncio
async def test_mimo_supervisor_parses_structured_tool_fallback_without_exposing_thoughts() -> None:
    decision = await MiMoSupervisor(provider=StructuredDecisionProvider()).decide(
        {"goal": "解释栈", "messages": [], "observations": [], "artifacts": []},
        [],
    )

    assert decision.status == "continue"
    assert decision.summary == "先检索课程资料"
    assert decision.tool_calls[0].name == "search_course_knowledge"
    assert decision.tool_calls[0].arguments == {"query": "栈", "top_k": 5}
    assert "private" not in decision.summary


class DirectUngroundedAnswerProvider:
    async def chat(self, messages, **kwargs):
        return ChatResponse(
            content='{"status":"complete","summary":"直接回答","final_answer":"栈是后进先出。"}'
        )


class EmptyArgumentToolProvider:
    async def chat(self, messages, **kwargs):
        return ChatResponse(
            content="",
            finish_reason="tool_calls",
            tool_calls=[ToolCall(id="call_empty", name="search_course_knowledge", arguments={})],
        )


@pytest.mark.asyncio
async def test_mimo_supervisor_requires_retrieval_for_explicitly_grounded_goal() -> None:
    decision = await MiMoSupervisor(provider=DirectUngroundedAnswerProvider()).decide(
        {
            "goal": "请基于课程资料解释栈，并给出引用。",
            "messages": [],
            "observations": [],
            "citations": [],
        },
        [
            {
                "type": "function",
                "function": {
                    "name": "search_course_knowledge",
                    "description": "检索",
                    "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
                },
            }
        ],
    )

    assert decision.status == "continue"
    assert decision.tool_calls[0].name == "search_course_knowledge"
    assert decision.tool_calls[0].arguments["query"] == "请基于课程资料解释栈，并给出引用。"


@pytest.mark.asyncio
async def test_mimo_supervisor_enforces_explicit_multi_tool_goal_until_satisfied() -> None:
    supervisor = MiMoSupervisor(provider=DirectUngroundedAnswerProvider())
    tools = [
        {
            "type": "function",
            "function": {"name": name, "description": name, "parameters": {"type": "object"}},
        }
        for name in ("generate_learning_path", "generate_quiz")
    ]
    first = await supervisor.decide(
        {"goal": "制定学习计划并生成练习题", "messages": [], "observations": [], "tool_calls": []},
        tools,
    )
    second = await supervisor.decide(
        {
            "goal": "制定学习计划并生成练习题",
            "messages": [],
            "observations": [{"success": True, "tool_name": "generate_learning_path"}],
            "tool_calls": [{"name": "generate_learning_path"}],
        },
        tools,
    )

    assert first.tool_calls[0].name == "generate_learning_path"
    assert first.tool_calls[0].arguments["goal"] == "制定学习计划并生成练习题"
    assert second.tool_calls[0].name == "generate_quiz"
    assert second.tool_calls[0].arguments["topic"] == "制定学习计划并生成练习题"


@pytest.mark.asyncio
async def test_mimo_supervisor_routes_explicit_strategy_apply_to_high_risk_tool() -> None:
    decision = await MiMoSupervisor(provider=DirectUngroundedAnswerProvider()).decide(
        {
            "goal": "应用最新的一条自进化策略，如果属于高风险操作必须等待确认。",
            "messages": [],
            "observations": [],
            "tool_calls": [],
        },
        [
            {
                "type": "function",
                "function": {
                    "name": "apply_evolution_strategy",
                    "description": "应用策略",
                    "parameters": {"type": "object"},
                },
            }
        ],
    )

    assert decision.status == "continue"
    assert decision.tool_calls[0].name == "apply_evolution_strategy"


@pytest.mark.asyncio
async def test_mimo_supervisor_fills_safe_arguments_for_selected_tool() -> None:
    decision = await MiMoSupervisor(provider=EmptyArgumentToolProvider()).decide(
        {"goal": "请检索二叉树资料", "messages": [], "observations": [], "tool_calls": []},
        [],
    )

    assert decision.tool_calls[0].arguments["query"] == "请检索二叉树资料"


def test_mimo_supervisor_normalizes_status_tool_args_shape() -> None:
    supervisor = MiMoSupervisor(provider=StructuredDecisionProvider())

    decision = supervisor._parse_decision(
        '{"status":"continue","summary":"先检索",'
        '"tool_calls":[{"tool":"search_course_knowledge","args":{"query":"栈"}}]}'
    )

    assert decision.status == "continue"
    assert decision.tool_calls[0].name == "search_course_knowledge"
    assert decision.tool_calls[0].arguments == {"query": "栈"}


def test_mimo_supervisor_executes_tools_even_when_structured_status_says_complete() -> None:
    supervisor = MiMoSupervisor(provider=StructuredDecisionProvider())

    decision = supervisor._parse_decision(
        '{"status":"complete","summary":"先回答","final_answer":"回答",'
        '"tool_calls":[{"name":"search_course_knowledge","arguments":{"query":"栈"}}]}'
    )

    assert decision.status == "continue"
    assert decision.tool_calls[0].name == "search_course_knowledge"


def test_mimo_supervisor_normalizes_quiz_question_types_to_service_contract() -> None:
    supervisor = MiMoSupervisor(provider=StructuredDecisionProvider())

    arguments = supervisor._safe_arguments(
        "generate_quiz",
        {"question_types": ["选择题", "fill_in_blank", "short_answer"]},
        "生成练习题",
    )

    assert arguments["question_types"] == ["single_choice", "fill_blank", "short_answer"]


class ApprovalSupervisor:
    def __init__(self) -> None:
        self.completed = False

    async def decide(self, state, tool_schemas):
        if state.get("observations"):
            return AgentDecision(
                status="complete",
                summary="高风险操作完成",
                final_answer="策略已应用。",
            )
        return AgentDecision(
            status="continue",
            summary="准备应用策略",
            tool_calls=[
                PlannedToolCall(
                    id="risk_call",
                    name="apply_evolution_strategy",
                    arguments={"strategy_id": str(uuid4())},
                )
            ],
        )


@pytest.mark.asyncio
async def test_langgraph_high_risk_tool_interrupts_and_resumes_from_checkpoint() -> None:
    executed = False

    async def apply_strategy(context: ToolContext, arguments: dict[str, object]) -> ToolExecutionResult:
        nonlocal executed
        executed = True
        return ToolExecutionResult(output={"status": "active"})

    registry = ToolRegistry()
    registry.register(
        AgentTool(
            name="apply_evolution_strategy",
            description="应用策略",
            agent_name="EvolutionAgent",
            input_schema={"type": "object", "properties": {}},
            handler=apply_strategy,
            risk_level="high",
            requires_confirmation=True,
        )
    )
    graph = LearningAgentGraph(registry=registry, supervisor=ApprovalSupervisor())
    thread_id = "thread-approval"
    interrupted = await graph.run(
        task_id=uuid4(),
        conversation_id=uuid4(),
        user_id=uuid4(),
        course_id=uuid4(),
        goal="应用策略",
        thread_id=thread_id,
    )

    assert interrupted["status"] == "waiting_confirmation"
    assert executed is False

    completed = await graph.resume(thread_id=thread_id, approved=True)

    assert completed["status"] == "completed"
    assert executed is True


def test_agent_persistence_models_support_conversations_events_and_dynamic_steps() -> None:
    assert AgentConversation.__tablename__ == "agent_conversations"
    assert AgentMessage.__tablename__ == "agent_messages"
    assert AgentTaskEvent.__tablename__ == "agent_task_events"
    assert {
        "conversation_id",
        "thread_id",
        "graph_version",
        "runtime_mode",
        "iteration_count",
        "tool_call_count",
        "replan_count",
        "last_event_at",
    }.issubset(AgentTask.__table__.columns.keys())
    assert {
        "tool_call_id",
        "parent_step_id",
        "iteration_no",
        "node_name",
        "decision_summary",
    }.issubset(AgentTaskStep.__table__.columns.keys())


def test_default_learning_tool_registry_exposes_specialized_agents_and_risk_boundaries() -> None:
    user = SimpleNamespace(id=uuid4(), role="student")
    registry = build_learning_tool_registry(SimpleNamespace(), user)  # type: ignore[arg-type]
    names = {item["function"]["name"] for item in registry.tool_schemas()}

    assert {
        "search_course_knowledge",
        "answer_course_question",
        "generate_learning_path",
        "generate_explanation",
        "generate_quiz",
        "analyze_learning_diagnosis",
        "refresh_recommendations",
        "rebuild_profile",
        "reflect_learning_memory",
        "review_artifacts",
        "apply_evolution_strategy",
    }.issubset(names)
    assert registry.requires_confirmation("apply_evolution_strategy") is True
    assert registry.risk_level("apply_evolution_strategy") == "high"


def test_unified_agent_conversation_api_routes_are_registered() -> None:
    from app.main import app

    paths = app.openapi()["paths"]
    assert {
        "/api/v1/agent/conversations",
        "/api/v1/agent/conversations/{conversation_id}/messages",
        "/api/v1/agent/tasks/{task_id}/events",
        "/api/v1/agent/tasks/{task_id}/resume",
        "/api/v1/agent/tasks/{task_id}/cancel",
    }.issubset(paths)


@pytest.mark.asyncio
async def test_tool_argument_validation_failure_becomes_observation_for_replanning() -> None:
    async def handler(context: ToolContext, arguments: dict[str, object]) -> ToolExecutionResult:
        return ToolExecutionResult(output={"unexpected": True})

    registry = ToolRegistry()
    registry.register(
        AgentTool(
            name="search_course_knowledge",
            description="检索课程知识库",
            agent_name="KnowledgeAgent",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            handler=handler,
        )
    )

    result = await registry.execute(
        "search_course_knowledge",
        {},
        ToolContext(task_id=uuid4(), tool_call_id="invalid_args", user_id=uuid4(), course_id=uuid4()),
    )

    assert result.success is False
    assert "缺少参数: query" in str(result.error_message)
    assert result.attempts == 1


@pytest.mark.asyncio
async def test_event_broker_falls_back_to_pubsub_when_redis_streams_are_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from redis.exceptions import ResponseError

    published: list[tuple[str, str]] = []

    class FakeRedis:
        async def xadd(self, *args, **kwargs):
            raise ResponseError("unknown command 'XADD'")

        async def expire(self, *args, **kwargs):
            return True

        async def publish(self, channel: str, payload: str):
            published.append((channel, payload))
            return 1

        async def aclose(self):
            return None

    import app.services.agent_queue_service as queue_module

    monkeypatch.setattr(queue_module.redis, "from_url", lambda *args, **kwargs: FakeRedis())
    task_id = uuid4()

    await AgentEventBroker("redis://example").publish(task_id, "planning", {"message": "开始"})

    assert published
    assert published[0][0] == f"agent:task:{task_id}:pubsub"
