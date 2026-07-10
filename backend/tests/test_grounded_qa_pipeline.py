from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.prompt import PromptVersion
from app.rag.evidence import EvidenceBundle, EvidenceItem, GraphContext
from app.schemas.tutor import TutorChatRequest, TutorChatResponse, TutorPerformance
from app.services.grounded_qa_pipeline import GroundedQaPipeline
from app.services.personalization_context_service import PersonalizationContextService
from app.services.prompt_service import (
    GROUNDED_TUTOR_RULES,
    PromptService,
    RenderedPrompt,
)


class _PromptResult:
    def __init__(self, value: object | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object | None:
        return self.value


class _PromptDB:
    def __init__(self, value: object | None = None) -> None:
        self.value = value

    async def execute(self, statement: object) -> _PromptResult:
        return _PromptResult(self.value)


@pytest.mark.asyncio
async def test_answer_uses_one_llm_call_and_no_sync_review() -> None:
    provider = SimpleNamespace(
        chat=AsyncMock(
            return_value=SimpleNamespace(
                content="栈遵循后进先出 [S1]。",
                model="mock",
                provider="mock",
                raw={},
            )
        )
    )
    pipeline = GroundedQaPipeline(db=None)  # type: ignore[arg-type]
    pipeline._authorize = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    pipeline._retrieve = AsyncMock(
        return_value=EvidenceBundle([], GraphContext(), 0)
    )
    pipeline._build_generation = AsyncMock(
        return_value=(provider, "grounded prompt", None)
    )
    pipeline._persist = AsyncMock(return_value=(None, None))
    pipeline.logs.start_run = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    pipeline.logs.finish_run = AsyncMock()

    result = await pipeline.answer(
        TutorChatRequest(course_id=uuid4(), question="什么是栈？"),
        SimpleNamespace(id=uuid4(), role="student"),
    )

    assert provider.chat.await_count == 1
    pipeline._retrieve.assert_awaited_once()
    provider.chat.assert_awaited_once()
    _, call_kwargs = provider.chat.await_args
    assert call_kwargs == {
        "temperature": 0.2,
        "max_tokens": 1200,
        "thinking": {"type": "disabled"},
        "prompt_version_id": None,
    }
    assert result.grounding_status == "insufficient"
    assert result.citations == []
    assert "[S1]" not in result.answer
    assert result.review_result["pass"] is False
    assert "未知引用编号：S1" in result.review_result["issues"]
    assert result.performance.llm_call_count == 1
    finish_payload = pipeline.logs.finish_run.await_args.kwargs["output_payload"]
    assert finish_payload["evidence_candidate_count"] == 0
    assert finish_payload["evidence_accepted_count"] == 0
    assert finish_payload["grounding_status"] == "insufficient"


@pytest.mark.asyncio
async def test_simple_greeting_skips_retrieval_and_llm() -> None:
    external_run_id = uuid4()
    pipeline = GroundedQaPipeline(db=None)  # type: ignore[arg-type]
    pipeline._authorize = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    pipeline._retrieve = AsyncMock()
    pipeline._persist = AsyncMock(return_value=(None, None))
    pipeline.logs.start_run = AsyncMock()
    pipeline.logs.finish_run = AsyncMock()

    result = await pipeline.answer(
        TutorChatRequest(course_id=uuid4(), question="你好"),
        SimpleNamespace(id=uuid4(), role="student"),
        agent_run_id=external_run_id,
    )

    pipeline._retrieve.assert_not_awaited()
    pipeline.logs.start_run.assert_not_awaited()
    pipeline.logs.finish_run.assert_not_awaited()
    assert result.provider == "local_intent_router"
    assert result.agent_run_id == external_run_id
    assert result.performance.llm_call_count == 0


@pytest.mark.asyncio
async def test_answer_reuses_external_agent_run_without_managing_log(
    monkeypatch,
) -> None:
    external_run_id = uuid4()
    provider = SimpleNamespace(
        chat=AsyncMock(
            return_value=SimpleNamespace(
                content="栈遵循后进先出。",
                model="mock",
                provider="mock",
                raw={},
            )
        )
    )
    pipeline = GroundedQaPipeline(db=None)  # type: ignore[arg-type]
    pipeline._authorize = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    pipeline._retrieve = AsyncMock(
        return_value=EvidenceBundle([], GraphContext(), 0)
    )
    render_prompt = AsyncMock(
        return_value=RenderedPrompt(content="grounded prompt")
    )
    monkeypatch.setattr(
        PromptService,
        "render_grounded_tutor_prompt",
        render_prompt,
    )
    provider_context = {}

    def fake_get_llm_provider(**kwargs):
        provider_context.update(kwargs)
        return provider

    import app.services.grounded_qa_pipeline as pipeline_module

    monkeypatch.setattr(
        pipeline_module,
        "get_llm_provider",
        fake_get_llm_provider,
    )
    pipeline._persist = AsyncMock(return_value=(None, None))
    pipeline.logs.start_run = AsyncMock()
    pipeline.logs.finish_run = AsyncMock()

    result = await pipeline.answer(
        TutorChatRequest(
            course_id=uuid4(),
            question="什么是栈？",
            use_profile=False,
        ),
        SimpleNamespace(id=uuid4(), role="student"),
        agent_run_id=external_run_id,
    )

    pipeline.logs.start_run.assert_not_awaited()
    pipeline.logs.finish_run.assert_not_awaited()
    assert provider_context["agent_run_id"] == external_run_id
    assert result.agent_run_id == external_run_id


@pytest.mark.asyncio
async def test_answer_keeps_only_markers_used_by_the_model() -> None:
    first = EvidenceItem(
        citation_key="S1",
        source_type="document",
        source_id=uuid4(),
        chunk_id=uuid4(),
        knowledge_id=uuid4(),
        title="栈讲义",
        quote="栈遵循后进先出。",
        retrieval_mode="vector",
        rerank_score=0.8,
        confidence="strong",
    )
    second = EvidenceItem(
        citation_key="S2",
        source_type="wiki",
        source_id=uuid4(),
        page_id=uuid4(),
        title="递归调用栈",
        quote="递归调用会保存现场。",
        retrieval_mode="wiki_match",
        confidence="acceptable",
    )
    bundle = EvidenceBundle([first, second], GraphContext(), 7)
    provider = SimpleNamespace(
        chat=AsyncMock(
            return_value=SimpleNamespace(
                content="递归调用会保存现场 [S2]，不存在的依据 [S9]。",
                model="qa-model",
                provider="primary",
                raw={
                    "fallback_used": True,
                    "failed_provider": "primary",
                    "fallback_reason": "timeout",
                },
            )
        )
    )
    pipeline = GroundedQaPipeline(db=None)  # type: ignore[arg-type]
    pipeline._authorize = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    pipeline._retrieve = AsyncMock(return_value=bundle)
    pipeline._build_generation = AsyncMock(return_value=(provider, "prompt", None))
    pipeline._persist = AsyncMock(return_value=(None, None))
    pipeline.logs.start_run = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    pipeline.logs.finish_run = AsyncMock()

    result = await pipeline.answer(
        TutorChatRequest(course_id=uuid4(), question="递归如何使用栈？"),
        SimpleNamespace(id=uuid4(), role="student"),
    )

    assert [citation.citation_key for citation in result.citations] == ["S2"]
    assert "[S9]" not in result.answer
    assert result.grounding_status == "partial"
    assert result.review_result["pass"] is False
    assert "未知引用编号：S9" in result.review_result["issues"]
    assert result.performance.evidence_candidate_count == 7
    assert result.performance.evidence_accepted_count == 2
    assert result.fallback_used is True
    assert result.failed_provider == "primary"
    assert result.fallback_reason == "timeout"
    assert result.related_knowledge_points[0].knowledge_id == str(first.knowledge_id)


@pytest.mark.asyncio
async def test_grounded_prompt_appends_rules_to_old_database_template() -> None:
    version = PromptVersion(
        id=uuid4(),
        agent_name="TutorAgent",
        scene="tutor.qa",
        version_no=1,
        template_content="旧 Tutor 模板：{question} / {wiki_context}",
        parameters_schema={},
        status="active",
        created_by="system",
    )
    rendered = await PromptService(_PromptDB(version)).render_grounded_tutor_prompt(  # type: ignore[arg-type]
        {"question": "什么是栈？", "wiki_context": "[S1] 栈讲义"}
    )

    assert rendered.source == "database"
    assert rendered.prompt_version_id == version.id
    assert (
        rendered.content
        == "旧 Tutor 模板：什么是栈？ / [S1] 栈讲义" + GROUNDED_TUTOR_RULES
    )


def test_personalization_formats_profile_and_memories_separately() -> None:
    context = {
        "global_profile": SimpleNamespace(profile_summary="偏好图示"),
        "course_profile": None,
        "preference": None,
        "strategies": {},
        "memories": [SimpleNamespace(content="曾混淆栈和队列")],
    }

    profile = PersonalizationContextService.format_profile_for_prompt(context)
    memories = PersonalizationContextService.format_memories_for_prompt(context)

    assert "偏好图示" in profile
    assert "曾混淆栈和队列" not in profile
    assert memories == "曾混淆栈和队列"


@pytest.mark.asyncio
async def test_persist_stub_preserves_requested_conversation_id() -> None:
    conversation_id = uuid4()
    pipeline = GroundedQaPipeline(db=None)  # type: ignore[arg-type]
    pipeline._authorize = AsyncMock(return_value=SimpleNamespace(id=uuid4()))

    result = await pipeline.answer(
        TutorChatRequest(
            course_id=uuid4(),
            conversation_id=conversation_id,
            question="你好",
        ),
        SimpleNamespace(id=uuid4(), role="student"),
    )

    assert result.message_id is None
    assert result.conversation_id == conversation_id
    assert result.postprocess_status == "skipped"


@pytest.mark.asyncio
async def test_stream_orders_evidence_before_delta_and_done() -> None:
    class FakeStreamProvider:
        provider_name = "mock"

        def __init__(self) -> None:
            self.calls = 0

        async def stream_chat(self, messages, **kwargs):
            self.calls += 1
            yield "栈遵循"
            yield "后进先出 [S1]。"

    evidence = EvidenceItem(
        citation_key="S1",
        source_type="document",
        source_id=uuid4(),
        chunk_id=uuid4(),
        title="数据结构讲义",
        quote="栈遵循后进先出原则。",
        confidence="strong",
    )
    bundle = EvidenceBundle([evidence], GraphContext(), 1)
    request = TutorChatRequest(course_id=uuid4(), question="什么是栈？")
    user = SimpleNamespace(id=uuid4(), role="student")
    provider = FakeStreamProvider()
    pipeline = GroundedQaPipeline(db=SimpleNamespace(rollback=AsyncMock()))  # type: ignore[arg-type]
    pipeline._authorize = AsyncMock(return_value=SimpleNamespace(id=request.course_id))
    pipeline._retrieve = AsyncMock(return_value=bundle)
    pipeline._build_generation = AsyncMock(return_value=(provider, "prompt", None))
    pipeline._complete_and_persist = AsyncMock(
        return_value=TutorChatResponse(
            answer="栈遵循后进先出 [S1]。",
            citations=[evidence.as_citation()],
            grounding_status="grounded",
            grounding_message="回答已绑定 1 条课程依据。",
            performance=TutorPerformance(llm_call_count=1),
        )
    )

    events = [event async for event in pipeline.stream(request, user)]

    names = [event["event"] for event in events]
    assert names == ["progress", "evidence", "progress", "delta", "delta", "progress", "done"]
    assert events[0]["data"]["stage"] == "retrieve_context"
    assert events[2]["data"]["stage"] == "llm_generation"
    assert events[-2]["data"]["stage"] == "validate_citations"
    assert events[-1]["data"]["performance"]["llm_call_count"] == 1
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_persistence_failure_keeps_answer_and_skips_postprocess() -> None:
    request = TutorChatRequest(course_id=uuid4(), question="什么是栈？")
    user = SimpleNamespace(id=uuid4(), role="student")
    expected = TutorChatResponse(answer="栈遵循后进先出原则。")
    db = SimpleNamespace(rollback=AsyncMock())
    pipeline = GroundedQaPipeline(db=db)  # type: ignore[arg-type]
    pipeline._persist = AsyncMock(side_effect=RuntimeError("database unavailable"))
    pipeline._publish_postprocess = AsyncMock()
    pipeline._answer_without_persistence = AsyncMock(
        return_value=(expected, SimpleNamespace(id=request.course_id))
    )

    result = await pipeline.answer(request, user)

    assert result.answer == expected.answer
    assert result.message_id is None
    assert result.postprocess_status == "skipped"
    db.rollback.assert_awaited_once()
    pipeline._publish_postprocess.assert_not_awaited()


@pytest.mark.asyncio
async def test_event_publish_failure_does_not_hide_committed_answer() -> None:
    request = TutorChatRequest(course_id=uuid4(), question="什么是栈？")
    expected = TutorChatResponse(answer="栈遵循后进先出原则。")
    record_id = uuid4()
    pipeline = GroundedQaPipeline(db=SimpleNamespace())  # type: ignore[arg-type]
    pipeline._answer_without_persistence = AsyncMock(
        return_value=(expected, SimpleNamespace(id=request.course_id))
    )
    pipeline._safe_persist = AsyncMock(return_value=(record_id, None))
    pipeline._publish_postprocess = AsyncMock(side_effect=RuntimeError("queue unavailable"))

    result = await pipeline.answer(
        request, SimpleNamespace(id=uuid4(), role="student")
    )

    assert result.answer == expected.answer
    assert result.message_id == record_id
    assert result.postprocess_status == "queued"


@pytest.mark.asyncio
async def test_persist_writes_learning_record_and_messages_in_one_commit() -> None:
    user_id = uuid4()
    course_id = uuid4()
    conversation_id = uuid4()
    record_id = uuid4()
    conversation = SimpleNamespace(id=conversation_id)
    record = SimpleNamespace(id=record_id)
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock(), rollback=AsyncMock())
    pipeline = GroundedQaPipeline(db=db)  # type: ignore[arg-type]
    pipeline.conversations.get_for_user = AsyncMock(return_value=conversation)
    pipeline.conversations.add_message = AsyncMock()
    pipeline.records.record_event = AsyncMock(return_value=record)
    response = TutorChatResponse(
        answer="栈遵循后进先出 [S1]。",
        citations=[{"citation_key": "S1", "source_type": "document", "title": "栈讲义"}],
        grounding_status="grounded",
        grounding_message="回答已绑定课程依据。",
        provider="mock",
        fallback_used=False,
    )
    payload = TutorChatRequest(
        course_id=course_id,
        conversation_id=conversation_id,
        question="什么是栈？",
    )

    result = await pipeline._persist(
        response=response,
        payload=payload,
        current_user=SimpleNamespace(id=user_id, role="student"),
        course=SimpleNamespace(id=course_id),
        persist_conversation_messages=True,
    )

    assert result == (record_id, conversation_id)
    assert pipeline.records.record_event.await_args.kwargs["commit"] is False
    learning_payload = pipeline.records.record_event.await_args.kwargs["event_payload"]
    assert learning_payload["answer"] == response.answer
    assert learning_payload["grounding_status"] == "grounded"
    assert pipeline.conversations.add_message.await_count == 2
    assistant_call = pipeline.conversations.add_message.await_args_list[1].kwargs
    assert assistant_call["role"] == "assistant"
    assert assistant_call["message_type"] == "tutor"
    assert assistant_call["payload"]["learning_record_id"] == str(record_id)
    assert assistant_call["payload"]["message_id"] == str(record_id)
    assert assistant_call["payload"]["conversation_id"] == str(conversation_id)
    assert assistant_call["payload"]["postprocess_status"] == "queued"
    assert assistant_call["payload"]["citations"][0]["citation_key"] == "S1"
    assert assistant_call["payload"]["performance"]["llm_call_count"] == 0
    db.commit.assert_awaited_once()
    assert db.refresh.await_count == 2


@pytest.mark.asyncio
async def test_persist_without_conversation_messages_still_records_learning() -> None:
    record = SimpleNamespace(id=uuid4())
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock(), rollback=AsyncMock())
    pipeline = GroundedQaPipeline(db=db)  # type: ignore[arg-type]
    pipeline.records.record_event = AsyncMock(return_value=record)
    pipeline.conversations.get_for_user = AsyncMock()
    pipeline.conversations.create = AsyncMock()
    pipeline.conversations.add_message = AsyncMock()
    conversation_id = uuid4()

    result = await pipeline._persist(
        response=TutorChatResponse(answer="回答"),
        payload=TutorChatRequest(
            course_id=uuid4(), question="问题", conversation_id=conversation_id
        ),
        current_user=SimpleNamespace(id=uuid4(), role="student"),
        course=SimpleNamespace(id=uuid4()),
        persist_conversation_messages=False,
    )

    assert result == (record.id, conversation_id)
    pipeline.records.record_event.assert_awaited_once()
    pipeline.conversations.get_for_user.assert_not_awaited()
    pipeline.conversations.create.assert_not_awaited()
    pipeline.conversations.add_message.assert_not_awaited()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_rolls_back_all_chat_writes_when_assistant_message_fails() -> None:
    conversation = SimpleNamespace(id=uuid4())
    record = SimpleNamespace(id=uuid4())
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock(), rollback=AsyncMock())
    pipeline = GroundedQaPipeline(db=db)  # type: ignore[arg-type]
    pipeline.conversations.get_for_user = AsyncMock(return_value=conversation)
    pipeline.conversations.add_message = AsyncMock(
        side_effect=[SimpleNamespace(id=uuid4()), RuntimeError("message write failed")]
    )
    pipeline.records.record_event = AsyncMock(return_value=record)
    payload = TutorChatRequest(
        course_id=uuid4(),
        conversation_id=conversation.id,
        question="什么是栈？",
    )

    result = await pipeline._persist(
        response=TutorChatResponse(answer="后进先出。"),
        payload=payload,
        current_user=SimpleNamespace(id=uuid4(), role="student"),
        course=SimpleNamespace(id=payload.course_id),
        persist_conversation_messages=True,
    )

    assert result == (None, conversation.id)
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_greeting_omits_evidence_and_model_call() -> None:
    request = TutorChatRequest(course_id=uuid4(), question="你好")
    pipeline = GroundedQaPipeline(db=SimpleNamespace(rollback=AsyncMock()))  # type: ignore[arg-type]
    pipeline._authorize = AsyncMock(return_value=SimpleNamespace(id=request.course_id))
    pipeline._retrieve = AsyncMock()
    pipeline._build_generation = AsyncMock()
    pipeline._safe_persist = AsyncMock(return_value=(None, None))

    events = [
        event
        async for event in pipeline.stream(
            request, SimpleNamespace(id=uuid4(), role="student")
        )
    ]

    assert [event["event"] for event in events] == [
        "progress",
        "progress",
        "delta",
        "progress",
        "done",
    ]
    pipeline._retrieve.assert_not_awaited()
    pipeline._build_generation.assert_not_awaited()
    assert events[-1]["data"]["provider"] == "local_intent_router"
