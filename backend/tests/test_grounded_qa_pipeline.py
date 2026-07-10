from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.prompt import PromptVersion
from app.rag.evidence import EvidenceBundle, EvidenceItem, GraphContext
from app.schemas.tutor import TutorChatRequest
from app.services.grounded_qa_pipeline import GroundedQaPipeline
from app.services.personalization_context_service import PersonalizationContextService
from app.services.prompt_service import GROUNDED_TUTOR_RULES, PromptService


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
    assert result.performance.llm_call_count == 1
    finish_payload = pipeline.logs.finish_run.await_args.kwargs["output_payload"]
    assert finish_payload["evidence_candidate_count"] == 0
    assert finish_payload["evidence_accepted_count"] == 0
    assert finish_payload["grounding_status"] == "insufficient"


@pytest.mark.asyncio
async def test_simple_greeting_skips_retrieval_and_llm() -> None:
    pipeline = GroundedQaPipeline(db=None)  # type: ignore[arg-type]
    pipeline._authorize = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    pipeline._retrieve = AsyncMock()
    pipeline._persist = AsyncMock(return_value=(None, None))

    result = await pipeline.answer(
        TutorChatRequest(course_id=uuid4(), question="你好"),
        SimpleNamespace(id=uuid4(), role="student"),
    )

    pipeline._retrieve.assert_not_awaited()
    assert result.provider == "local_intent_router"
    assert result.performance.llm_call_count == 0


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
    assert result.grounding_status == "grounded"
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
