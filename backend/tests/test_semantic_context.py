from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.agent_runtime.intent_contract import build_intent_frame
from app.services.conversation_context_service import ConversationContext
from app.services.intent_understanding_service import IntentUnderstandingService, SemanticIntent
from app.services.semantic_summary_service import selected_excerpt, SemanticSummaryService, SummarySelection


@pytest.mark.asyncio
async def test_semantic_contract_keeps_authorized_tools_and_original_source(monkeypatch):
    message_id = uuid4()
    frame = build_intent_frame(goal="栈和队列各出练习题", request_message_id=message_id).model_dump(mode="json")
    monkeypatch.setattr("app.services.intent_understanding_service.PromptService.render_prompt",
                        AsyncMock(return_value=SimpleNamespace(content="prompt", prompt_version_id=None)))
    provider = SimpleNamespace(structured_chat=AsyncMock(return_value=SemanticIntent(mode="execute", tasks=[
        {"topic": "栈", "segment": "栈练习", "tools": ["generate_quiz"]},
        {"topic": "队列", "segment": "队列练习", "tools": ["generate_quiz"]},
    ])))
    tools = [{"function": {"name": "generate_quiz"}}]
    result = await IntentUnderstandingService(None).resolve(goal="栈和队列各出练习题", frame=frame,
        context=ConversationContext(), provider=provider, tools=tools)
    assert result["parser"] == "semantic_v1" and len(result["tasks"]) == 2
    assert all(item["source_message_id"] == str(message_id) for item in result["tasks"])
    provider.structured_chat.assert_awaited_once()


@pytest.mark.asyncio
async def test_semantic_parser_cannot_expand_excluded_capability(monkeypatch):
    frame = build_intent_frame(goal="帮我安排一下", request_message_id=uuid4(), skip_tools=["generate_quiz"]).model_dump(mode="json")
    monkeypatch.setattr("app.services.intent_understanding_service.PromptService.render_prompt",
                        AsyncMock(return_value=SimpleNamespace(content="prompt", prompt_version_id=None)))
    provider = SimpleNamespace(structured_chat=AsyncMock(return_value=SemanticIntent(mode="execute", tasks=[
        {"topic": "栈", "segment": "栈练习", "tools": ["generate_quiz"]},
    ])))
    result = await IntentUnderstandingService(None).resolve(goal="帮我安排一下", frame=frame,
        context=ConversationContext(), provider=provider, tools=[{"function": {"name": "generate_quiz"}}])
    assert result["parser"] == "rule_candidates_v1"
    assert "semantic_understanding_unavailable" in result["uncertainty"]


@pytest.mark.asyncio
async def test_ordinary_question_has_no_extra_understanding_call():
    provider = SimpleNamespace(structured_chat=AsyncMock())
    frame = build_intent_frame(goal="递归终止条件是什么？", request_message_id=uuid4()).model_dump(mode="json")
    await IntentUnderstandingService(None).resolve(goal="递归终止条件是什么？", frame=frame,
        context=ConversationContext(), provider=provider, tools=[])
    provider.structured_chat.assert_not_awaited()


def test_summary_selection_cannot_invent_or_drop_opening_goal():
    lines = ["学生原话：目标是复习数据结构", "产物1", "目标2", "请求3", "最新问题"]
    assert lines[0] in selected_excerpt(lines, [4])
    assert "最新问题" in selected_excerpt(lines, [4])
    with pytest.raises(ValueError):
        selected_excerpt(lines, [99])


@pytest.mark.asyncio
async def test_forget_during_semantic_selection_fences_stale_summary(monkeypatch):
    conversation = SimpleNamespace(summary="学生原话：旧目标", course_id=uuid4(),
        extra_meta={"context_compaction_v1": {"version": 1}})
    monkeypatch.setattr("app.services.semantic_summary_service.AgentConversationRepository.get_for_user",
                        AsyncMock(return_value=conversation))
    monkeypatch.setattr("app.services.semantic_summary_service.AgentConversationRepository.get_for_user_locked",
                        AsyncMock(return_value=conversation))
    monkeypatch.setattr("app.services.semantic_summary_service.PromptService.render_prompt",
                        AsyncMock(return_value=SimpleNamespace(content="prompt", prompt_version_id=None)))
    async def selecting(*args, **kwargs):
        conversation.extra_meta = {}
        conversation.summary = None
        return SummarySelection(selected_indices=[0])
    monkeypatch.setattr("app.services.semantic_summary_service.get_llm_provider",
                        lambda **kwargs: SimpleNamespace(structured_chat=selecting))
    db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    assert not await SemanticSummaryService(db).compact(uuid4(), uuid4())
    assert conversation.summary is None
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_memory_extraction_aligns_existing_facts_for_the_correct_owner(monkeypatch):
    from app.agents.memory_agent import MemoryAgent
    from app.agents.structured_outputs import MemoryReflectOutput
    owner, course = uuid4(), uuid4()
    known = AsyncMock(return_value=[])
    monkeypatch.setattr("app.repositories.memory_repository.MemoryRepository.reconciliation_candidates", known)
    monkeypatch.setattr("app.agents.memory_agent.PromptService.render_prompt", AsyncMock(return_value=SimpleNamespace(content="prompt", prompt_version_id=None)))
    monkeypatch.setattr("app.agents.memory_agent.call_structured_chat_or_none", AsyncMock(return_value=MemoryReflectOutput(memories=[])))
    records = [SimpleNamespace(id=uuid4(), course_id=course, event_type="chat", event_payload={"question": "我喜欢简短讲解"})]
    result = await MemoryAgent(SimpleNamespace(execute=AsyncMock()))._llm_reflect(SimpleNamespace(), records, user_id=owner)
    assert result == []
    known.assert_awaited_once_with(owner, course)
