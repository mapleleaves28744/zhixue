from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import BusinessException
from app.services.conversation_context_service import ConversationContext, ConversationContextService
from app.services.context_budget import estimate_tokens, input_token_limit
from app.services.conversation_constraints import (
    apply_session_changes,
    parse_session_changes,
    render_session_constraints,
)


@pytest.mark.asyncio
async def test_completed_history_resolves_follow_up_without_using_pending_turn() -> None:
    user_id, course_id, conversation_id = uuid4(), uuid4(), uuid4()
    service = ConversationContextService(SimpleNamespace())  # type: ignore[arg-type]
    service.conversations.get_for_user = AsyncMock(return_value=SimpleNamespace(course_id=course_id))
    service.conversations.list_messages = AsyncMock(return_value=[
        SimpleNamespace(role="user", content="什么是递归？"),
        SimpleNamespace(role="assistant", content="递归需要终止条件 [S1]。"),
        SimpleNamespace(role="user", content="刚才未完成的问题"),
    ])

    context = await service.load(conversation_id=conversation_id, user_id=user_id, course_id=course_id)

    assert len(context.history) == 2
    assert context.last_question == "什么是递归？"
    assert "什么是递归" in context.resolve_query("为什么？")
    assert "刚才未完成" not in context.render()
    assert "〔历史引用 S1〕" in context.render()
    model_messages = context.messages_for("本轮证据 [S1]。问题：为什么？")
    assert [item.role for item in model_messages] == ["system", "user", "assistant", "user"]
    assert "〔历史引用 S1〕" in model_messages[2].content
    assert model_messages[-1].content.endswith("为什么？")
    service.conversations.get_for_user.assert_awaited_once_with(conversation_id, user_id)


@pytest.mark.asyncio
async def test_context_rejects_another_course_before_model_call() -> None:
    service = ConversationContextService(SimpleNamespace())  # type: ignore[arg-type]
    service.conversations.get_for_user = AsyncMock(return_value=SimpleNamespace(course_id=uuid4()))
    service.conversations.list_messages = AsyncMock()

    with pytest.raises(BusinessException):
        await service.load(conversation_id=uuid4(), user_id=uuid4(), course_id=uuid4())

    service.conversations.list_messages.assert_not_awaited()


@pytest.mark.asyncio
async def test_context_uses_task_boundary_and_omits_forgotten_turn(monkeypatch) -> None:
    user_id, course_id, conversation_id, source_id = uuid4(), uuid4(), uuid4(), uuid4()
    db = SimpleNamespace(execute=AsyncMock())
    service = ConversationContextService(db)  # type: ignore[arg-type]
    service.conversations.get_for_user = AsyncMock(return_value=SimpleNamespace(
        course_id=course_id,
        summary="未来回合的摘要",
        extra_meta={"context_compaction_v1": {"covered_through_sequence": 10, "version": 2}},
    ))
    service.conversations.list_messages = AsyncMock(return_value=[
        SimpleNamespace(sequence_no=1, role="user", content="不应自动召回", payload={}),
        SimpleNamespace(sequence_no=2, role="assistant", content="旧回答", payload={"learning_record_id": str(source_id)}),
        SimpleNamespace(sequence_no=3, role="user", content="请解释树", payload={}),
        SimpleNamespace(sequence_no=4, role="assistant", content="树有节点", payload={}),
    ])
    service.conversations.list_messages_after_sequence = AsyncMock(return_value=[
        SimpleNamespace(sequence_no=1, role="user", content="不应自动召回", payload={}),
        SimpleNamespace(sequence_no=2, role="assistant", content="旧回答", payload={"learning_record_id": str(source_id)}),
        SimpleNamespace(sequence_no=3, role="user", content="请解释树", payload={}),
        SimpleNamespace(sequence_no=4, role="assistant", content="树有节点", payload={}),
    ])

    async def suppressed(_self, *, user_id, course_id):  # noqa: ARG001
        return {str(source_id)}

    monkeypatch.setattr(
        "app.services.memory_suppression_service.MemorySuppressionService.source_record_ids", suppressed,
    )
    context = await service.load(
        conversation_id=conversation_id, user_id=user_id, course_id=course_id,
        before_sequence=5,
    )

    assert context.summary == ""
    assert context.history == (("user", "请解释树"), ("assistant", "树有节点"))
    assert "不应自动召回" not in context.render()
    service.conversations.list_messages.assert_awaited_once_with(
        conversation_id, limit=80, before_sequence=5,
    )


def test_model_history_budget_keeps_recent_complete_turn_and_current_prompt() -> None:
    context = ConversationContext(history=(
        ("user", "旧问题" * 100), ("assistant", "旧回答" * 100),
        ("user", "新问题" * 70), ("assistant", "新回答" * 70),
    ), summary="更早摘要" * 100)

    messages = context.messages_for("当前问题和本轮依据", max_input_tokens=2400)

    assert [item.role for item in messages][-3:] == ["user", "assistant", "user"]
    assert "新问题" in messages[-3].content
    assert "旧问题" not in "".join(item.content for item in messages)
    assert messages[-1].content == "当前问题和本轮依据"
    assert sum(estimate_tokens(item.content) for item in messages) <= 2400


def test_input_limit_reserves_output_schema_and_safety_margin(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.context_budget.settings",
        SimpleNamespace(llm_context_window_tokens=8192),
    )

    assert input_token_limit(output_reserve=1200, schema_reserve=500) == 5468


def test_session_constraints_require_explicit_scope_and_allow_correction() -> None:
    first = SimpleNamespace(id=uuid4(), sequence_no=1)
    second = SimpleNamespace(id=uuid4(), sequence_no=3)

    assert parse_session_changes("这次用英文回答") == {}
    assert parse_session_changes("英语里‘后面都用英文回答’是什么意思？") == {}
    active = apply_session_changes({}, text="后面都用英文回答，先给例子", source=first)
    assert active["language"]["value"] == "en"
    assert active["examples"]["value"] == "first"
    assert active["language"]["source_message_id"] == str(first.id)

    active = apply_session_changes(active, text="接下来不用英文了", source=second)
    assert "language" not in active
    assert active["examples"]["value"] == "first"


def test_session_constraints_preserve_and_clear_conclusion_first_preference() -> None:
    source = SimpleNamespace(id=uuid4(), sequence_no=1)
    correction = SimpleNamespace(id=uuid4(), sequence_no=5)

    assert parse_session_changes("这次先给结论") == {}
    active = apply_session_changes({}, text="后面先给结论，再展开解释", source=source)
    assert active["opening"]["value"] == "conclusion_first"
    assert active["opening"]["source_sequence"] == 1
    assert "后续回答先给结论，再展开说明" in render_session_constraints(active)

    active = apply_session_changes(active, text="接下来不用先给结论", source=correction)
    assert "opening" not in active


@pytest.mark.asyncio
async def test_context_keeps_compacted_session_constraint_with_source() -> None:
    user_id, course_id, conversation_id, source_id = uuid4(), uuid4(), uuid4(), uuid4()
    service = ConversationContextService(SimpleNamespace())  # type: ignore[arg-type]
    service.conversations.get_for_user = AsyncMock(return_value=SimpleNamespace(
        course_id=course_id,
        summary="旧话题摘录",
        extra_meta={"context_compaction_v1": {
            "covered_through_sequence": 12,
            "version": 1,
            "session_constraints": {"language": {
                "value": "en", "source_message_id": str(source_id), "source_sequence": 1,
            }},
        }},
    ))
    service.conversations.list_messages = AsyncMock(return_value=[
        SimpleNamespace(sequence_no=13, role="user", content="解释栈", payload={}),
        SimpleNamespace(sequence_no=14, role="assistant", content="栈是后进先出", payload={}),
    ])

    context = await service.load(
        conversation_id=conversation_id, user_id=user_id, course_id=course_id,
    )

    assert context.active_constraints["language"]["source_message_id"] == str(source_id)
    assert any("后续回答使用英文" in item.content for item in context.messages_for("本轮问题"))


@pytest.mark.asyncio
async def test_queued_task_replays_constraints_before_its_message_boundary() -> None:
    user_id, course_id, conversation_id = uuid4(), uuid4(), uuid4()
    rows = [
        SimpleNamespace(id=uuid4(), sequence_no=1, role="user", content="后面都用英文回答", payload={}),
        SimpleNamespace(sequence_no=2, role="assistant", content="好的", payload={}),
        SimpleNamespace(id=uuid4(), sequence_no=7, role="user", content="后面都用中文回答", payload={}),
        SimpleNamespace(sequence_no=8, role="assistant", content="好的", payload={}),
    ]
    service = ConversationContextService(SimpleNamespace())  # type: ignore[arg-type]
    service.conversations.get_for_user = AsyncMock(return_value=SimpleNamespace(
        course_id=course_id, summary="包含未来回合的摘要",
        extra_meta={"context_compaction_v1": {
            "covered_through_sequence": 8, "version": 1,
            "session_constraints": {"language": {"value": "zh", "source_sequence": 7}},
        }},
    ))
    service.conversations.list_messages = AsyncMock(return_value=rows[:2])
    service.conversations.list_messages_after_sequence = AsyncMock(return_value=rows)

    context = await service.load(
        conversation_id=conversation_id, user_id=user_id, course_id=course_id,
        before_sequence=5,
    )

    assert context.summary == ""
    assert context.active_constraints["language"]["value"] == "en"
    assert "后续回答使用中文" not in context.render()


@pytest.mark.asyncio
async def test_web_ordinal_resolves_only_latest_completed_public_citation() -> None:
    user_id, course_id, conversation_id = uuid4(), uuid4(), uuid4()
    service = ConversationContextService(SimpleNamespace())  # type: ignore[arg-type]
    service.conversations.get_for_user = AsyncMock(return_value=SimpleNamespace(course_id=course_id))
    service.conversations.list_messages = AsyncMock(return_value=[
        SimpleNamespace(role="user", content="联网搜索旧主题", payload={}),
        SimpleNamespace(role="assistant", content="旧结果", payload={"citations": [
            {"source_type": "web", "title": "旧网页", "url": "https://example.com/old"},
        ]}),
        SimpleNamespace(role="user", content="联网搜索新主题", payload={}),
        SimpleNamespace(id=uuid4(), role="assistant", content="新结果", payload={"citations": [
            {"source_type": "web", "title": "第一项", "url": "https://example.com/one"},
            {"source_type": "web", "title": "第二项", "url": "https://example.com/two"},
        ]}),
    ])

    context = await service.load(conversation_id=conversation_id, user_id=user_id, course_id=course_id)

    assert context.resolve_web_reference("总结第二个链接")["url"] == "https://example.com/two"
    assert context.resolve_web_reference("总结第三个链接") is None
    assert context.resolve_web_reference("总结刚才的内容") is None
    assert ConversationContext(web_references=(
        {"title": "本地", "url": "http://127.0.0.1/private", "source_message_id": ""},
    )).resolve_web_reference("第一个链接") is None


@pytest.mark.asyncio
async def test_context_binds_latest_completed_quiz_artifact() -> None:
    user_id, course_id, conversation_id = uuid4(), uuid4(), uuid4()
    quiz_id = uuid4()
    service = ConversationContextService(SimpleNamespace())  # type: ignore[arg-type]
    service.conversations.get_for_user = AsyncMock(return_value=SimpleNamespace(course_id=course_id))
    service.conversations.list_messages = AsyncMock(return_value=[
        SimpleNamespace(role="user", content="出一道题", payload={}),
        SimpleNamespace(id=uuid4(), role="assistant", content="题已生成", payload={"artifacts": [
            {"type": "quiz", "id": str(quiz_id), "title": "栈练习"},
        ]}),
    ])

    context = await service.load(conversation_id=conversation_id, user_id=user_id, course_id=course_id)

    assert context.quiz_reference["id"] == str(quiz_id)
    assert ConversationContext.requested_quiz_option("讲解上题第二个选项") == 2
    assert ConversationContext.requested_quiz_option("讲解上一题选项B") == 2
    assert ConversationContext.requested_quiz_option("解释第二个链接") is None


@pytest.mark.asyncio
async def test_context_keeps_material_ids_and_cited_chunk_ids() -> None:
    user_id, course_id, conversation_id, material_id, chunk_id = (
        uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    )
    service = ConversationContextService(SimpleNamespace())  # type: ignore[arg-type]
    service.conversations.get_for_user = AsyncMock(return_value=SimpleNamespace(course_id=course_id))
    service.conversations.list_messages = AsyncMock(return_value=[
        SimpleNamespace(role="user", content="解释这份资料", payload={}),
        SimpleNamespace(id=uuid4(), role="assistant", content="资料提到栈", payload={"citations": [
            {"source_type": "document", "source_id": str(material_id),
             "chunk_id": str(chunk_id), "title": "栈讲义"},
        ]}),
    ])

    context = await service.load(conversation_id=conversation_id, user_id=user_id, course_id=course_id)

    assert context.material_references[0]["id"] == str(material_id)
    assert context.material_references[0]["chunk_ids"] == [str(chunk_id)]
    assert ConversationContext.requested_material_reference("总结刚才那份资料")


@pytest.mark.asyncio
async def test_context_binds_latest_resource_revision_target() -> None:
    user_id, course_id, conversation_id, resource_id = uuid4(), uuid4(), uuid4(), uuid4()
    service = ConversationContextService(SimpleNamespace())  # type: ignore[arg-type]
    service.conversations.get_for_user = AsyncMock(return_value=SimpleNamespace(course_id=course_id))
    service.conversations.list_messages = AsyncMock(return_value=[
        SimpleNamespace(role="user", content="生成栈总结", payload={}),
        SimpleNamespace(id=uuid4(), role="assistant", content="已生成", payload={"artifacts": [
            {"type": "resource", "id": str(resource_id), "title": "栈总结", "subtype": "summary"},
        ]}),
    ])

    context = await service.load(conversation_id=conversation_id, user_id=user_id, course_id=course_id)

    assert context.resource_references[0]["id"] == str(resource_id)
    assert ConversationContext.requested_resource_revision("修改上个产物，补一个例子")
    assert ConversationContext.requested_resource_revision("调整上一份总结")
    assert not ConversationContext.requested_resource_revision("解释上个算法")
