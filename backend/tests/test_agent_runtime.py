from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agent_runtime.graph import LearningAgentGraph
from app.agent_runtime.service_tools import build_learning_tool_registry
from app.agent_runtime.state import AgentDecision, PlannedToolCall
from app.agent_runtime.supervisor import MiMoSupervisor
from app.services.conversation_intent import is_simple_greeting
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


def test_explicit_course_source_qa_plans_only_grounded_answer() -> None:
    from app.agent_runtime.supervisor_intents import plan_required_tools

    assert plan_required_tools(
        "基于课程资料解释栈并给出引用",
        is_profile_update_only=False,
    ) == ["answer_course_question"]


@pytest.mark.parametrize(
    "goal",
    [
        "请检索课程资料中所有提到栈的片段",
        "请在课程知识库中搜索递归",
        "查找栈相关片段",
    ],
)
def test_explicit_search_only_goal_keeps_standalone_search(goal: str) -> None:
    from app.agent_runtime.supervisor_intents import plan_required_tools

    assert plan_required_tools(goal, is_profile_update_only=False) == ["search_course_knowledge"]


@pytest.mark.asyncio
async def test_answer_tool_final_answer_bypasses_second_supervisor_call() -> None:
    class OneDecisionSupervisor:
        def __init__(self) -> None:
            self.calls = 0

        async def decide(self, state, tool_schemas):
            self.calls += 1
            if self.calls > 1:
                raise AssertionError("grounded answer must not be summarized again")
            return AgentDecision(
                status="continue",
                summary="调用共享问答内核",
                plan=["回答课程问题"],
                tool_calls=[
                    PlannedToolCall(
                        id="qa-1",
                        name="answer_course_question",
                        arguments={"question": "解释栈"},
                    )
                ],
            )

    async def answer_handler(context, arguments):
        return ToolExecutionResult(
            output={"answer": "栈是 LIFO [S1]。"},
            final_answer="栈是 LIFO [S1]。",
            citations=[{"citation_key": "S1"}],
        )

    supervisor = OneDecisionSupervisor()
    registry = ToolRegistry()
    registry.register(
        AgentTool(
            name="answer_course_question",
            description="答疑",
            agent_name="TutorAgent",
            input_schema={"type": "object", "properties": {}},
            handler=answer_handler,
        )
    )
    result = await LearningAgentGraph(registry=registry, supervisor=supervisor).run(
        task_id=uuid4(),
        conversation_id=uuid4(),
        user_id=uuid4(),
        course_id=uuid4(),
        goal="解释栈",
        thread_id="grounded-pass-through",
    )

    assert result["final_answer"] == "栈是 LIFO [S1]。"
    assert supervisor.calls == 1


def test_agent_runtime_no_longer_extracts_dialogue_synchronously() -> None:
    source = (Path(__file__).resolve().parents[1] / "app/services/agent_runtime_service.py").read_text(
        encoding="utf-8"
    )
    assert "extract_knowledge_from_dialogue(" not in source


@pytest.mark.asyncio
async def test_answer_tool_reuses_grounded_pipeline_without_conversation_messages(monkeypatch) -> None:
    from app.schemas.tutor import TutorChatResponse
    import app.services.grounded_qa_pipeline as pipeline_module

    calls: list[tuple[object, object, bool]] = []

    class FakePipeline:
        def __init__(self, db) -> None:
            self.db = db

        async def answer(self, payload, current_user, *, persist_conversation_messages=True):
            calls.append((payload, current_user, persist_conversation_messages))
            return TutorChatResponse(
                answer="栈是后进先出 [S1]。",
                citations=[
                    {
                        "citation_key": "S1",
                        "source_type": "document",
                        "title": "数据结构讲义",
                    }
                ],
                grounding_status="grounded",
                grounding_message="回答已由课程资料支持。",
                message_id=uuid4(),
            )

    monkeypatch.setattr(pipeline_module, "GroundedQaPipeline", FakePipeline)
    user = SimpleNamespace(id=uuid4())
    registry = build_learning_tool_registry(SimpleNamespace(), user)  # type: ignore[arg-type]
    conversation_id = uuid4()
    result = await registry.execute(
        "answer_course_question",
        {"question": "解释栈"},
        ToolContext(
            task_id=uuid4(),
            tool_call_id="qa-shared",
            user_id=user.id,
            course_id=uuid4(),
            conversation_id=conversation_id,
        ),
    )

    assert result.success is True
    assert result.final_answer == "栈是后进先出 [S1]。"
    assert calls[0][0].conversation_id == conversation_id
    assert calls[0][2] is False


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
async def test_result_saver_failure_does_not_rerun_committed_tool() -> None:
    handler_calls = 0

    async def committed_handler(context, arguments):
        nonlocal handler_calls
        handler_calls += 1
        return ToolExecutionResult(output={"message_id": "record-1"}, final_answer="已提交回答")

    async def failing_saver(key, result):
        raise RuntimeError("step persistence unavailable")

    registry = ToolRegistry(result_saver=failing_saver)
    registry.register(
        AgentTool(
            name="answer_course_question",
            description="课程答疑",
            agent_name="TutorAgent",
            input_schema={"type": "object", "properties": {}},
            handler=committed_handler,
            writes_db=True,
            max_retries=2,
        )
    )

    result = await registry.execute(
        "answer_course_question",
        {},
        ToolContext(task_id=uuid4(), tool_call_id="qa-save-fail", user_id=uuid4(), course_id=uuid4()),
    )

    assert result.success is True
    assert result.final_answer == "已提交回答"
    assert handler_calls == 1


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


@pytest.mark.asyncio
async def test_langgraph_agent_completes_when_memory_reflection_fails() -> None:
    async def failing_memory_reflector(state):
        raise RuntimeError("memory schema validation failed")

    class CompleteSupervisor:
        async def decide(self, state, tool_schemas):
            return AgentDecision(
                status="complete",
                summary="直接完成",
                final_answer="队列是先进先出的线性结构。",
            )

    events: list[tuple[str, dict[str, object]]] = []

    async def event_sink(event_type, state, payload):
        events.append((event_type, payload))

    graph = LearningAgentGraph(
        registry=ToolRegistry(),
        supervisor=CompleteSupervisor(),
        memory_reflector=failing_memory_reflector,
        event_sink=event_sink,
    )

    result = await graph.run(
        task_id=uuid4(),
        conversation_id=uuid4(),
        user_id=uuid4(),
        course_id=uuid4(),
        goal="解释队列",
        thread_id="thread-memory-reflect-fallback",
    )

    assert result["status"] == "completed"
    assert result["final_answer"] == "队列是先进先出的线性结构。"
    reflected = [payload for event_type, payload in events if event_type == "memory_reflected"]
    assert reflected
    assert reflected[-1]["status"] == "skipped"
    assert "memory schema validation failed" in str(reflected[-1]["error_message"])


@pytest.mark.asyncio
async def test_simple_greeting_skips_provider_review_and_memory_reflection() -> None:
    class ProviderThatMustNotRun:
        async def chat(self, messages, **kwargs):
            raise AssertionError("simple greeting must not call the LLM supervisor")

    review_called = False
    memory_called = False

    async def reviewer(state):
        nonlocal review_called
        review_called = True
        return {}

    async def memory_reflector(state):
        nonlocal memory_called
        memory_called = True
        return {}

    graph = LearningAgentGraph(
        registry=ToolRegistry(),
        supervisor=MiMoSupervisor(provider=ProviderThatMustNotRun()),
        reviewer=reviewer,
        memory_reflector=memory_reflector,
    )

    result = await graph.run(
        task_id=uuid4(),
        conversation_id=uuid4(),
        user_id=uuid4(),
        course_id=uuid4(),
        goal="你好",
        thread_id="thread-simple-greeting",
    )

    assert is_simple_greeting("你好") is True
    assert result["status"] == "completed"
    assert "你好" in result["final_answer"]
    assert review_called is False
    assert memory_called is False


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


class DuplicateCompletedToolProvider:
    async def chat(self, messages, **kwargs):
        return ChatResponse(
            content="",
            finish_reason="tool_calls",
            tool_calls=[
                ToolCall(
                    id="call_duplicate",
                    name="search_course_knowledge",
                    arguments={"query": "解释二叉树"},
                )
            ],
        )


@pytest.mark.asyncio
async def test_mimo_supervisor_handles_duplicate_completed_tool_calls_without_crashing() -> None:
    decision = await MiMoSupervisor(provider=DuplicateCompletedToolProvider()).decide(
        {
            "goal": "解释二叉树",
            "messages": [],
            "observations": [
                {
                    "success": True,
                    "tool_name": "search_course_knowledge",
                    "output": {"chunks": [{"content": "二叉树是每个节点最多有两个子节点的树结构。"}]},
                }
            ],
            "artifacts": [],
            "tool_calls": [{"name": "search_course_knowledge"}],
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

    assert decision.status == "complete"
    assert decision.tool_calls == []
    assert "执行详情" in decision.final_answer


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
            },
            {
                "type": "function",
                "function": {
                    "name": "answer_course_question",
                    "description": "可信课程答疑",
                    "parameters": {"type": "object", "properties": {"question": {"type": "string"}}},
                },
            },
        ],
    )

    assert decision.status == "continue"
    assert decision.tool_calls[0].name == "answer_course_question"
    assert decision.tool_calls[0].arguments["question"] == "请基于课程资料解释栈，并给出引用。"


@pytest.mark.asyncio
async def test_mimo_supervisor_replaces_native_search_for_explicit_grounded_qa() -> None:
    decision = await MiMoSupervisor(provider=FakeProvider()).decide(
        {
            "goal": "基于课程资料解释栈并给出引用",
            "messages": [],
            "observations": [],
            "citations": [],
        },
        [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": name,
                    "parameters": {"type": "object", "properties": {}},
                },
            }
            for name in ("search_course_knowledge", "answer_course_question")
        ],
    )

    assert [call.name for call in decision.tool_calls] == ["answer_course_question"]


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
async def test_mimo_supervisor_routes_dialogue_profile_updates_to_profile_tool() -> None:
    decision = await MiMoSupervisor(provider=DirectUngroundedAnswerProvider()).decide(
        {
            "goal": "我是软件工程大二学生，我喜欢 Python 代码示例，递归比较薄弱，请记住我的学习偏好。",
            "messages": [],
            "observations": [],
            "tool_calls": [],
        },
        [
            {
                "type": "function",
                "function": {
                    "name": "update_profile_from_dialogue",
                    "description": "从对话中提取画像",
                    "parameters": {"type": "object"},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "rebuild_profile",
                    "description": "重建画像",
                    "parameters": {"type": "object"},
                },
            },
        ],
    )

    assert decision.status == "continue"
    assert decision.tool_calls[0].name == "update_profile_from_dialogue"
    assert "软件工程" in decision.tool_calls[0].arguments["dialogue_text"]


class ProfileOverreachProvider:
    async def chat(self, messages, **kwargs):
        return ChatResponse(
            content="",
            finish_reason="tool_calls",
            tool_calls=[
                ToolCall(id="profile", name="update_profile_from_dialogue", arguments={}),
                ToolCall(id="quiz", name="generate_quiz", arguments={"topic": "递归"}),
            ],
        )


@pytest.mark.asyncio
async def test_mimo_supervisor_keeps_profile_only_request_to_one_tool_and_then_completes() -> None:
    supervisor = MiMoSupervisor(provider=ProfileOverreachProvider())
    goal = "我是软件工程大二学生，递归比较薄弱，请记住我的学习偏好。"
    tools = [
        {
            "type": "function",
            "function": {"name": name, "description": name, "parameters": {"type": "object"}},
        }
        for name in ("update_profile_from_dialogue", "generate_quiz")
    ]

    first = await supervisor.decide(
        {"goal": goal, "messages": [], "observations": [], "tool_calls": []},
        tools,
    )
    completed = await supervisor.decide(
        {
            "goal": goal,
            "messages": [],
            "observations": [{"success": True, "tool_name": "update_profile_from_dialogue"}],
            "tool_calls": [{"name": "update_profile_from_dialogue"}],
        },
        tools,
    )

    assert [item.name for item in first.tool_calls] == ["update_profile_from_dialogue"]
    assert completed.status == "complete"
    assert completed.tool_calls == []


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
        "update_profile_from_dialogue",
        "rebuild_profile",
        "reflect_learning_memory",
        "review_artifacts",
        "apply_evolution_strategy",
        "parse_uploaded_document",
        "generate_mindmap",
        "generate_diagram",
        "transcribe_audio",
        "synthesize_speech",
    }.issubset(names)
    assert registry.requires_confirmation("apply_evolution_strategy") is True
    assert registry.risk_level("apply_evolution_strategy") == "high"


def test_generate_explanation_artifact_refs_keep_resource_type_for_frontend_categories() -> None:
    source = (Path(__file__).resolve().parents[1] / "app/agent_runtime/service_tools.py").read_text(
        encoding="utf-8"
    )

    assert '"resource_type": data.get("resource_type")' in source
    assert '"resource_id": str(result.resource_id)' in source


def test_parse_uploaded_document_requires_explicit_material_id_and_is_not_faked_by_supervisor() -> None:
    user = SimpleNamespace(id=uuid4(), role="student")
    registry = build_learning_tool_registry(SimpleNamespace(), user)  # type: ignore[arg-type]
    tool = registry.get("parse_uploaded_document")
    supervisor = MiMoSupervisor(provider=StructuredDecisionProvider())

    assert tool.input_schema["required"] == ["material_id"]
    assert supervisor._safe_arguments("parse_uploaded_document", {}, "解析这份课程资料") == {}


def test_supervisor_routes_speech_explanation_requests() -> None:
    supervisor = MiMoSupervisor(provider=DirectUngroundedAnswerProvider())
    goal = "生成讲解队列的语音"
    required = supervisor._required_tools(goal)

    assert supervisor._speech_intent(goal)
    assert "generate_explanation" in required
    assert "synthesize_speech" in required
    assert required.index("generate_explanation") < required.index("synthesize_speech")


def test_supervisor_resolve_speech_text_uses_explanation_output() -> None:
    supervisor = MiMoSupervisor(provider=DirectUngroundedAnswerProvider())
    state = {
        "observations": [
            {
                "tool_name": "generate_explanation",
                "success": True,
                "output": {"content": "队列是一种先进先出的线性结构。" * 3},
            }
        ]
    }
    text = supervisor._resolve_speech_text(state, "生成讲解队列的语音")
    assert "队列" in text
    assert len(text) >= 40


@pytest.mark.asyncio
async def test_mimo_supervisor_routes_visual_resource_requests_to_mermaid_tools() -> None:
    supervisor = MiMoSupervisor(provider=DirectUngroundedAnswerProvider())
    tools = [
        {
            "type": "function",
            "function": {"name": name, "description": name, "parameters": {"type": "object"}},
        }
        for name in ("generate_mindmap", "generate_diagram")
    ]

    mindmap = await supervisor.decide(
        {"goal": "请为二叉树生成思维导图", "messages": [], "observations": [], "tool_calls": []},
        tools,
    )
    diagram = await supervisor.decide(
        {"goal": "请画一张栈入栈出栈流程图", "messages": [], "observations": [], "tool_calls": []},
        tools,
    )

    assert mindmap.tool_calls[0].name == "generate_mindmap"
    assert mindmap.tool_calls[0].arguments == {"topic": "请为二叉树生成思维导图", "scope": "course", "depth": 3}
    assert diagram.tool_calls[0].name == "generate_diagram"
    assert diagram.tool_calls[0].arguments["concept"] == "请画一张栈入栈出栈流程图"


def test_unified_agent_conversation_api_routes_are_registered() -> None:
    from app.main import app

    paths = app.openapi()["paths"]
    assert {
        "/api/v1/agent/conversations",
        "/api/v1/agent/conversations/{conversation_id}/messages",
        "/api/v1/agent/tasks/{task_id}/events",
        "/api/v1/agent/tasks/{task_id}/resume",
        "/api/v1/agent/tasks/{task_id}/cancel",
        "/api/v1/agent/tasks/{task_id}/requeue",
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
    assert "校验失败" in str(result.error_message)
    assert "query" in str(result.error_message)
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
