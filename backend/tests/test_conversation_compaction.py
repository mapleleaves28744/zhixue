from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.conversation_summary_service import ConversationSummaryService
from app.services.conversation_turns import completed_turn_blocks
from app.services.conversation_context_service import ConversationContextService


def _message(sequence: int, role: str, content: str, *, request_id=None, payload=None):
    return SimpleNamespace(
        sequence_no=sequence, role=role, content=content,
        client_request_id=request_id if role == "assistant" else None,
        payload={**(payload or {}), **({"client_request_id": str(request_id)} if request_id and role == "user" else {})},
    )


def test_compaction_waits_for_all_interleaved_requests() -> None:
    first, second = uuid4(), uuid4()
    rows = [
        _message(1, "user", "先解释递归", request_id=first),
        _message(2, "user", "再解释栈", request_id=second),
        _message(3, "assistant", "栈的回答", request_id=second),
        _message(4, "assistant", "递归的回答", request_id=first),
    ]

    blocks = completed_turn_blocks(rows)

    assert len(blocks) == 1
    assert blocks[0][0] == 4
    assert [turn.user.content for turn in blocks[0][1]] == ["先解释递归", "再解释栈"]


def test_compaction_excludes_forgotten_source_and_preserves_coverage() -> None:
    forgotten = str(uuid4())
    rows = [
        _message(1, "user", "我不想再看到这段学习情况"),
        _message(2, "assistant", "已回答", payload={"learning_record_id": forgotten}),
        _message(3, "user", "请解释数组"),
        _message(4, "assistant", "数组按下标访问"),
    ]

    blocks = ConversationSummaryService._closed_blocks(rows, {forgotten})

    assert [block[1] for block in blocks] == [1, 1]
    assert blocks[0][2] == []
    assert blocks[1][2] == ["请解释数组"]


def test_compaction_does_not_promote_stable_preference_to_summary() -> None:
    rows = [
        _message(1, "user", "以后请一直用图解释"),
        _message(2, "assistant", "好的"),
    ]

    blocks = ConversationSummaryService._closed_blocks(rows)

    assert blocks[0][1] == 1
    assert blocks[0][2] == []


def test_unknown_keyed_reply_does_not_close_another_request() -> None:
    expected, unrelated = uuid4(), uuid4()
    rows = [
        _message(1, "user", "真正的请求", request_id=expected),
        _message(2, "assistant", "其他请求的回复", request_id=unrelated),
    ]

    assert completed_turn_blocks(rows) == []


async def _no_suppression(_self, *, user_id, course_id):  # noqa: ARG001
    return set()


def _rows_after(rows, after_sequence, *, limit):
    return [item for item in rows if item.sequence_no > after_sequence][:limit]


@pytest.mark.asyncio
async def test_compaction_projects_explicit_session_constraint(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.memory_suppression_service.MemorySuppressionService.source_record_ids",
        _no_suppression,
    )
    rows = []
    for index in range(15):
        rows.extend((
            _message(index * 2 + 1, "user", "后面都用英文回答" if index == 0 else f"问题{index}"),
            _message(index * 2 + 2, "assistant", "好的"),
        ))
    conversation = SimpleNamespace(
        summary=None, extra_meta={}, next_message_sequence=30, course_id=uuid4(),
    )
    db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    service = ConversationSummaryService(db)  # type: ignore[arg-type]
    service.conversations.get_for_user_locked = AsyncMock(return_value=conversation)
    service.conversations.list_messages_after_sequence = AsyncMock(
        side_effect=lambda conversation_id, after_sequence, *, limit: _rows_after(
            rows, after_sequence, limit=limit,
        )
    )
    service.conversations.get_message_by_sequence = AsyncMock(return_value=rows[-1])

    changed = await service.maybe_compact(conversation_id=uuid4(), user_id=uuid4())

    assert changed is True
    assert conversation.extra_meta["context_compaction_v1"]["session_constraints"]["language"]["value"] == "en"
    assert "后面都用英文回答" not in conversation.summary


@pytest.mark.asyncio
async def test_thirty_turn_compaction_keeps_goal_corrected_preference_and_latest_focus(monkeypatch) -> None:
    user_id, course_id, conversation_id = uuid4(), uuid4(), uuid4()
    rows = []
    for index in range(30):
        if index == 0:
            question = "我在复习数据结构，请后面都用英文回答"
        elif index == 15:
            question = "接下来都用中文回答"
        elif index == 28:
            question = "现在解释二叉树"
        elif index == 29:
            question = "继续说明刚才这个知识点"
        else:
            question = f"围绕当前知识点继续讲解，第 {index + 1} 轮"
        rows.extend((
            _message(index * 2 + 1, "user", question),
            _message(index * 2 + 2, "assistant", f"第 {index + 1} 轮回答"),
        ))

    async def no_suppression(_self, *, user_id, course_id):  # noqa: ARG001
        return set()

    monkeypatch.setattr(
        "app.services.memory_suppression_service.MemorySuppressionService.source_record_ids",
        no_suppression,
    )
    conversation = SimpleNamespace(
        summary=None,
        extra_meta={},
        next_message_sequence=60,
        course_id=course_id,
    )
    db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock(), execute=AsyncMock())
    summary_service = ConversationSummaryService(db)  # type: ignore[arg-type]
    summary_service.conversations.get_for_user_locked = AsyncMock(return_value=conversation)
    summary_service.conversations.list_messages_after_sequence = AsyncMock(
        side_effect=lambda _conversation_id, after_sequence, *, limit: _rows_after(
            rows, after_sequence, limit=limit,
        )
    )
    summary_service.conversations.get_message_by_sequence = AsyncMock(return_value=rows[-1])

    assert await summary_service.maybe_compact(conversation_id=conversation_id, user_id=user_id)
    projection = conversation.extra_meta["context_compaction_v1"]
    assert projection["covered_through_sequence"] >= 40
    assert projection["session_constraints"]["language"]["value"] == "zh"

    context_service = ConversationContextService(db)  # type: ignore[arg-type]
    context_service.conversations.get_for_user = AsyncMock(return_value=conversation)
    context_service.conversations.list_messages = AsyncMock(return_value=rows)
    context = await context_service.load(
        conversation_id=conversation_id,
        user_id=user_id,
        course_id=course_id,
    )
    messages = context.messages_for("本轮问题：它有哪些遍历方法？")
    rendered = "\n".join(item.content for item in messages)

    assert context.last_question == "继续说明刚才这个知识点"
    assert "二叉树" in "\n".join(content for _, content in context.history)
    assert "上文讨论：继续说明刚才这个知识点" in context.resolve_query("它有哪些遍历方法？")
    assert "数据结构" in context.summary
    assert "后续回答使用中文" in rendered
    assert "后续回答使用英文" not in rendered
    assert messages[-1].content == "本轮问题：它有哪些遍历方法？"
