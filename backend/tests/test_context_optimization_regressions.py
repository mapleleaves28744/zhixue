from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.agent_runtime.supervisor_intents import plan_required_tools
from app.agent_runtime.supervisor_completion import normalize_completion_answer
from app.services.conversation_constraints import parse_session_changes
from app.services.conversation_history_service import ConversationHistoryService
from app.repositories.agent_conversation_repository import AgentConversationRepository
from app.services.memory_suppression_service import MemorySuppressionService


@pytest.mark.parametrize("question", ["请总结我们刚才讨论的两个知识点。", "接着说刚才这个知识点的复杂度。", "它和队列有什么区别？"])
def test_context_followups_use_answer_kernel(question):
    assert plan_required_tools(question, is_profile_update_only=False) == ["answer_course_question"]


def test_search_result_cannot_replace_completed_grounded_answer():
    state = {"observations": [
        {"success": True, "tool_name": "answer_course_question", "output": {"answer": "栈后进先出"}},
        {"success": True, "tool_name": "search_course_knowledge", "output": {"items": []}},
    ]}
    assert normalize_completion_answer(state, "总结刚才的讨论", "其他回答") == "栈后进先出"


def test_question_after_separate_session_instruction_keeps_constraint():
    assert parse_session_changes("后续用英文，简短回答。栈是什么？") == {"language": "en", "detail": "concise"}
    assert parse_session_changes("后续用英文好吗？") == {}
    assert parse_session_changes("资料写着：后续用英文。栈是什么？") == {}


@pytest.mark.asyncio
async def test_history_search_keeps_source_scope_and_filters_forgotten_turn(monkeypatch):
    user_id, course_id, conversation_id, task_id = [uuid4() for _ in range(4)]
    source = SimpleNamespace(id=uuid4(), conversation_id=conversation_id, sequence_no=1,
                             role="user", content="学生喜欢用图", created_at=datetime.now(UTC))
    safe = SimpleNamespace(id=uuid4(), conversation_id=conversation_id, sequence_no=3,
                           role="user", content="栈的概念", created_at=datetime.now(UTC))
    monkeypatch.setattr(AgentConversationRepository, "get_task_user_message", AsyncMock(return_value=SimpleNamespace(sequence_no=9)))
    query = AsyncMock(return_value=[source, safe])
    monkeypatch.setattr(AgentConversationRepository, "search_owned_history", query)
    monkeypatch.setattr(AgentConversationRepository, "suppressed_history_message_ids", AsyncMock(return_value={source.id}))
    monkeypatch.setattr(MemorySuppressionService, "source_record_ids", AsyncMock(return_value={str(uuid4())}))
    items = await ConversationHistoryService(object()).search(user_id=user_id, course_id=course_id,
        query="栈", conversation_id=conversation_id, task_id=task_id)
    assert [item["message_id"] for item in items] == [str(safe.id)]
    assert query.await_args.kwargs["user_id"] == user_id
    assert query.await_args.kwargs["course_id"] == course_id
    assert query.await_args.kwargs["before_sequence"] == 9


def test_semantic_contract_tools_survive_keyword_candidate_filtering():
    from app.agent_runtime.tool_selector import select_tool_schemas
    names = ["search_course_knowledge", "generate_explanation", "generate_quiz"]
    state = {"goal": "先检索图的资料，再生成讲解和一组练习题", "intent_frame_v1": {
        "parser": "semantic_v1", "mode": "execute", "tasks": [{"tools": names}]}}
    schemas = [{"function": {"name": name}} for name in names]
    assert {item["function"]["name"] for item in select_tool_schemas(state, schemas)} == set(names)
    state["skip_tools"] = ["generate_quiz"]
    assert "generate_quiz" not in {item["function"]["name"] for item in select_tool_schemas(state, schemas)}


def test_completed_resources_are_not_hidden_by_empty_grounding_search():
    state = {"artifacts": [{"type": "resource", "title": "栈讲解"}, {"type": "resource", "title": "队列讲解"}],
             "observations": [{"tool_name": "search_course_knowledge", "success": True, "output": {"items": []}}]}
    answer = normalize_completion_answer(state, "各生成一份讲解", "未找到相关结果")
    assert "栈讲解" in answer and "队列讲解" in answer
    assert "未找到相关结果" not in answer


def test_resource_heading_never_uses_code_comments_as_title():
    from app.agents.resource_agent import ResourceAgent
    agent = ResourceAgent(None)
    assert agent._extract_title("## 归并排序讲解\n```python\n# 输出: [1, 2]\n```", resource_type="explanation", knowledge_name="归并排序") == "归并排序讲解"
    assert agent._extract_title("```python\n# 输出: [1, 2]\n```", resource_type="explanation", knowledge_name="归并排序") == "归并排序讲解"


@pytest.mark.asyncio
async def test_supervisor_continues_missing_contract_delivery_after_quiz_completed():
    from app.agent_runtime.supervisor import MiMoSupervisor
    provider = SimpleNamespace(chat=AsyncMock())
    state = {"goal": "生成图的讲解和练习题", "tool_call_count": 1, "intent_frame_v1": {
        "mode": "execute", "tasks": [{"id": "s1", "topic": "图", "segment": "图的讲解", "tools": ["generate_explanation"]},
                                      {"id": "s2", "topic": "图", "segment": "图的练习", "tools": ["generate_quiz"]}]},
        "tool_calls": [{"id": "c1", "name": "generate_quiz", "arguments": {"topic": "图"}}],
        "observations": [{"tool_call_id": "c1", "tool_name": "generate_quiz", "success": True, "artifact_refs": [{"id": "q1"}]}]}
    result = await MiMoSupervisor(provider).decide(state, [{"function": {"name": "generate_explanation"}}, {"function": {"name": "generate_quiz"}}])
    assert result.status == "continue" and result.tool_calls[0].name == "generate_explanation"
    assert result.tool_calls[0].arguments["topic"] == "图"
    provider.chat.assert_not_awaited()
