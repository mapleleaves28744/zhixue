from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from evaluation_budget import BudgetExceeded, BudgetProvider, EvaluationLedger
from app.llm.schemas import ChatMessage, ChatResponse
from app.services.conversation_constraints import parse_session_changes
from app.services.conversation_context_service import ConversationContext


def test_budget_reserves_pending_calls_across_restart(tmp_path):
    path = tmp_path / "budget.sqlite"
    ledger = EvaluationLedger(path, 100)
    identity = ledger.reserve("case", 70)
    restarted = EvaluationLedger(path, 100)
    with pytest.raises(BudgetExceeded):
        restarted.reserve("other", 31)
    restarted.finish(identity, elapsed=0, error=TimeoutError())
    assert restarted.snapshot()["charged_tokens"] == 70
    with pytest.raises(ValueError):
        restarted.finish(identity, elapsed=0)


def test_concurrent_budget_reservations_cannot_overspend(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    ledger = EvaluationLedger(tmp_path / "budget.sqlite", 100)
    def reserve(index):
        try:
            ledger.reserve(str(index), 30)
            return True
        except BudgetExceeded:
            return False
    with ThreadPoolExecutor(max_workers=10) as pool:
        assert sum(pool.map(reserve, range(10))) == 3
    assert ledger.snapshot()["charged_tokens"] == 90


def test_unknown_tokenizer_does_not_claim_exact_model_tokens():
    from app.services.context_budget import estimate_tokens
    assert estimate_tokens("随机ASCII-23D!@") >= len("随机ASCII-23D!@".encode("utf-8"))


def test_polluted_rule_topic_requires_semantic_validation():
    from app.services.intent_understanding_service import needs_semantic_understanding
    from app.agent_runtime.intent_contract import build_intent_frame
    from uuid import uuid4
    goal = "请围绕栈生成一份讲解资料"
    frame = build_intent_frame(goal=goal, request_message_id=uuid4()).model_dump(mode="json")
    assert needs_semantic_understanding(goal, frame, ConversationContext())


def test_actual_usage_releases_unused_reservation(tmp_path):
    ledger = EvaluationLedger(tmp_path / "budget.sqlite", 100)
    identity = ledger.reserve("case", 90)
    ledger.finish(identity, response=ChatResponse(content="x", model="test", usage={"total_tokens": 10}), elapsed=1)
    assert ledger.snapshot()["charged_tokens"] == 10
    ledger.reserve("next", 90)


def test_missing_usage_keeps_full_charge(tmp_path):
    ledger = EvaluationLedger(tmp_path / "budget.sqlite", 100)
    identity = ledger.reserve("case", 70)
    ledger.finish(identity, response=ChatResponse(content="x", model="test", usage={}), elapsed=1)
    assert ledger.snapshot()["charged_tokens"] == 70


@pytest.mark.asyncio
async def test_every_structured_retry_accounted(tmp_path):
    ledger = EvaluationLedger(tmp_path / "budget.sqlite", 10000)
    responses = iter(["invalid", '{"value":1}'])
    async def chat(*args, **kwargs):
        assert kwargs["transport_attempts"] == 1
        return ChatResponse(content=next(responses), model="test", usage={"total_tokens": 12})
    from pydantic import BaseModel
    class Output(BaseModel):
        value: int
    provider = BudgetProvider(SimpleNamespace(chat=chat, provider_name="test"), ledger)
    result = await provider.structured_chat([ChatMessage(role="user", content="test")], Output, max_tokens=20, max_retries=1)
    assert result.value == 1
    assert ledger.snapshot()["calls"]["succeeded"]["count"] == 2


@pytest.mark.parametrize("text,expected", [
    ("后续不要简短，详细讲解", {"detail": "detailed"}),
    ("接下来不用英文，用中文回答", {"language": "zh"}),
    ("以后分点回答。后续先给结论。为什么栈先进后出？", {"format": "bullets", "opening": "conclusion_first"}),
    ("资料写着：后续用英文", {}),
    ("后续用英文好吗？", {}),
    ("后续用中文。资料写着：接下来用英文。", {"language": "zh"}),
])
def test_explicit_constraints(text, expected):
    assert parse_session_changes(text) == expected


def test_material_reference_ordinal_and_ambiguity():
    first = {"id": "a", "title": "第一章.pdf"}
    second = {"id": "b", "title": "第二章.pdf"}
    context = ConversationContext(material_references=(first, second))
    assert context.resolve_material_reference("总结第二份资料") == second
    assert context.resolve_material_reference("讲解刚才那份资料第一章.pdf") == first
    assert context.resolve_material_reference("刚才那份资料") is None
    assert context.resolve_material_reference("第九份资料") is None


def test_byte_budget_handles_code_and_emoji(monkeypatch):
    from app.services import context_budget
    monkeypatch.setattr(context_budget, "_tokenizer", lambda _: None)
    for value in ("aF17zB08" * 30, "👩‍💻" * 20, "汉字" * 100):
        assert context_budget.estimate_tokens(value) >= len(value.encode("utf-8"))


def test_mandatory_prompt_cannot_overflow_budget():
    from app.core.exceptions import BusinessException
    with pytest.raises(BusinessException):
        ConversationContext().messages_for("x" * 1000, max_input_tokens=100)


def test_earlier_goal_gets_reserved_summary_space():
    context = ConversationContext(history=(("user", "近期问题" * 100), ("assistant", "近期回答" * 100)),
                                  summary="最初目标：目标标记ABC")
    messages = context.messages_for("当前请求", max_input_tokens=1600)
    assert "目标标记ABC" in "".join(message.content for message in messages)


@pytest.mark.parametrize("text,key", [("喜欢可视化学习", "diagrams"), ("希望通过具体案例理解", "examples"),
                                       ("讲得细一点", "detailed"), ("喜欢言简意赅", "concise")])
def test_memory_preference_aliases(text, key):
    from app.services.memory_facts import canonical_preference
    assert canonical_preference(text) == "preference:explanation:" + key


@pytest.mark.parametrize("text,allowed", [("后续用英文回答", False), ("不要长期记住我喜欢用图", False),
    ("这一次给我详细解释", False), ("请长期记住，我喜欢用图", True), ("我喜欢分步骤讲解", True)])
def test_memory_source_guards(text, allowed):
    from app.services.memory_facts import learning_memory_source_allowed
    assert learning_memory_source_allowed(text) is allowed


@pytest.mark.asyncio
async def test_session_only_memory_record_never_calls_llm(monkeypatch):
    from app.agents.memory_agent import MemoryAgent
    from unittest.mock import AsyncMock
    from uuid import uuid4
    model = AsyncMock()
    monkeypatch.setattr("app.agents.memory_agent.call_structured_chat_or_none", model)
    record = SimpleNamespace(id=uuid4(), event_type="chat", event_payload={"question": "后续用英文回答"})
    assert await MemoryAgent(None)._llm_reflect(SimpleNamespace(), [record], user_id=uuid4()) == []
    model.assert_not_awaited()


@pytest.mark.asyncio
async def test_semantic_revision_cannot_revive_old_topic(monkeypatch):
    from app.services.intent_understanding_service import IntentUnderstandingService, SemanticIntent
    from app.agent_runtime.intent_contract import build_intent_frame
    from unittest.mock import AsyncMock
    from uuid import uuid4
    goal = "给栈出练习题\n学生最新修订（优先于之前要求）：改为队列的讲解资源"
    frame = build_intent_frame(goal=goal, request_message_id=uuid4()).model_dump(mode="json")
    prompt = AsyncMock(return_value=SimpleNamespace(content="prompt", prompt_version_id=None))
    monkeypatch.setattr("app.services.intent_understanding_service.PromptService.render_prompt", prompt)
    provider = SimpleNamespace(structured_chat=AsyncMock(return_value=SemanticIntent(mode="execute", tasks=[
        {"topic": "栈", "segment": "旧主题", "tools": ["generate_explanation"]}])))
    result = await IntentUnderstandingService(None).resolve(goal=goal, frame=frame, context=ConversationContext(),
        provider=provider, tools=[{"function": {"name": "generate_explanation"}}])
    assert result["mode"] == "clarify" and not result["tasks"]
    assert prompt.call_args.kwargs["params"]["goal"] == "改为队列的讲解资源"


@pytest.mark.asyncio
async def test_runtime_applies_conservative_semantic_fallback(monkeypatch):
    from app.services.agent_runtime_service import AgentRuntimeService
    from unittest.mock import AsyncMock
    from uuid import uuid4
    frame = {"mode": "execute", "parser": "rule_candidates_v1", "tasks": [
        {"topic": "旧主题", "tools": ["generate_quiz"]}]}
    task = SimpleNamespace(id=uuid4(), user_id=uuid4(), course_id=uuid4(), conversation_id=uuid4(),
        status="running", task_goal="改为新主题", input_payload={"intent_frame_v1": frame})
    user = SimpleNamespace(id=task.user_id)
    message = SimpleNamespace(id=uuid4(), sequence_no=3)
    db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    service = AgentRuntimeService(db, broker=SimpleNamespace(publish=AsyncMock()))
    service.tasks = SimpleNamespace(claim_queued_task=AsyncMock(return_value=True))
    service.conversations = SimpleNamespace(get_task_user_message=AsyncMock(return_value=message),
        add_event=AsyncMock(return_value=SimpleNamespace(payload={}, sequence_no=1)),
        get_for_user_locked=AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_get_task", AsyncMock(return_value=task))
    monkeypatch.setattr(service, "_get_user", AsyncMock(return_value=user))
    monkeypatch.setattr(service, "_finish_task", AsyncMock())
    monkeypatch.setattr(service, "_publish_direct_completion", AsyncMock())
    monkeypatch.setattr("app.services.agent_runtime_service.ConversationContextService.load",
        AsyncMock(return_value=ConversationContext(last_question="旧主题")))
    monkeypatch.setattr("app.services.agent_runtime_service.get_llm_provider", lambda **kwargs: object())
    monkeypatch.setattr("app.services.agent_runtime_service.build_learning_tool_registry",
        lambda *args, **kwargs: SimpleNamespace(tool_schemas=lambda: []))
    fallback = {**frame, "mode": "clarify", "tasks": [], "revision": 1,
        "clarification_question": "请补充新主题"}
    monkeypatch.setattr("app.services.intent_understanding_service.IntentUnderstandingService.resolve",
        AsyncMock(return_value=fallback))
    result = await service.execute(task.id)
    assert result["final_answer"] == "请补充新主题"
    assert task.input_payload["intent_frame_v1"]["tasks"] == []


@pytest.mark.asyncio
async def test_answer_comparison_descriptions_do_not_authorize_tools(monkeypatch):
    from app.services.intent_understanding_service import IntentUnderstandingService, SemanticIntent
    from app.agent_runtime.intent_contract import build_intent_frame
    from unittest.mock import AsyncMock
    from uuid import uuid4
    context = ConversationContext(history=(("user", "请解释链表"),), last_question="请解释链表")
    goal = "它和数组有什么区别？"
    frame = build_intent_frame(goal=goal, request_message_id=uuid4()).model_dump(mode="json")
    monkeypatch.setattr("app.services.intent_understanding_service.PromptService.render_prompt",
        AsyncMock(return_value=SimpleNamespace(content="prompt", prompt_version_id=None)))
    provider = SimpleNamespace(structured_chat=AsyncMock(return_value=SemanticIntent(mode="answer", tasks=[
        {"topic": "链表与数组比较", "segment": goal, "tools": ["not_an_available_tool"]}],
        resolved_goal="比较链表与数组")))
    result = await IntentUnderstandingService(None).resolve(goal=goal, frame=frame, context=context, provider=provider, tools=[])
    assert result["mode"] == "answer" and result["tasks"] == []
    assert result["parser"] == "semantic_v1"


@pytest.mark.asyncio
async def test_supervisor_model_identity_comes_from_response(monkeypatch):
    from app.agent_runtime.supervisor import MiMoSupervisor
    async def chat(*args, **kwargs):
        return ChatResponse(content='{"status":"complete","summary":"完成","final_answer":"回答","model":"forged"}',
            model="actual-model", provider="actual-provider", usage={}, raw={})
    supervisor = MiMoSupervisor(SimpleNamespace(chat=chat))
    monkeypatch.setattr(supervisor, "_apply_safety_net", lambda state, tools, decision: decision)
    await supervisor.decide({"goal": "开放讨论", "messages": [], "observations": [], "tool_calls": []}, [])
    assert supervisor.last_answer_metadata["model"] == "actual-model"
    await supervisor.decide({"goal": "你好"}, [])
    assert not supervisor.last_answer_metadata


def test_material_batches_cover_every_source_character():
    from app.services.material_summary_service import source_batches
    chunks = [SimpleNamespace(id="one", page_no=1, content="中" * 100),
              SimpleNamespace(id="two", page_no=2, content="末尾独有事实")]
    batches = source_batches(chunks, byte_limit=150, max_batches=10)
    assert all(len(part.encode("utf-8")) <= 150 for part in batches)
    assert sum(part.count("中") for part in batches) == 100
    assert "末尾独有事实" in "".join(batches)
    with pytest.raises(ValueError):
        source_batches(chunks, byte_limit=150, max_batches=1)


@pytest.mark.asyncio
async def test_material_summary_includes_tail_and_rejects_fallback(monkeypatch):
    from app.services.material_summary_service import MaterialSummaryService
    from unittest.mock import AsyncMock
    monkeypatch.setattr("app.services.material_summary_service.PromptService.render_prompt",
        AsyncMock(side_effect=lambda **kwargs: SimpleNamespace(content=kwargs["params"]["content"], prompt_version_id=None)))
    async def chat(messages, **kwargs):
        return ChatResponse(content="摘要：" + messages[0].content[-80:], model="test", usage={}, raw={})
    chunks = [SimpleNamespace(id="one", page_no=1, content="示例" * 9000 + "末尾事实")]
    answer = await MaterialSummaryService(None).summarize(chunks=chunks, title="资料", question="全文总结",
        provider=SimpleNamespace(chat=chat))
    assert "末尾事实" in answer
    async def fallback(*args, **kwargs):
        return ChatResponse(content="Mock", model="test", usage={}, raw={"fallback_used": True})
    with pytest.raises(ValueError):
        await MaterialSummaryService(None).summarize(chunks=chunks, title="资料", question="总结",
            provider=SimpleNamespace(chat=fallback))
