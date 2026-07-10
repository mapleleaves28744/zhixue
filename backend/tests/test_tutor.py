"""Phase 14 tests: tutor schemas and formatting helpers."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

from app.api.v1.tutor import _stream_tutor_chat
from app.agents.tutor_agent import TutorAgent
from app.schemas.tutor import (
    TutorChatRequest,
    TutorChatResponse,
    TutorFeedbackRequest,
    TutorSaveToWikiRequest,
)
from app.services.tutor_service import TutorService
from app.services.conversation_intent import is_simple_greeting


def test_tutor_chat_request_defaults() -> None:
    course_id = uuid4()
    request = TutorChatRequest(course_id=course_id, question="递归为什么和栈有关？")

    assert request.course_id == course_id
    assert request.top_k == 5
    assert request.use_rag is True
    assert request.use_wiki is True
    assert request.use_profile is True
    assert request.stream is False


def test_tutor_chat_response_accepts_structured_evidence() -> None:
    response = TutorChatResponse(
        answer="递归依赖调用栈保存现场。",
        citations=[{"source_type": "wiki", "title": "递归调用栈", "page_id": str(uuid4())}],
        related_knowledge_points=[{"name": "递归调用栈"}],
        follow_up_questions=["能给一个例题吗？"],
        review_result={"pass": True, "risk_level": "low"},
        memory_update_suggestion={"should_reflect": True},
    )

    assert response.citations[0].source_type == "wiki"
    assert response.related_knowledge_points[0].name == "递归调用栈"


def test_tutor_save_and_feedback_requests() -> None:
    page_id = uuid4()
    save_request = TutorSaveToWikiRequest(wiki_page_id=page_id)
    feedback_request = TutorFeedbackRequest(feedback_type="useful", rating=5)

    assert save_request.wiki_page_id == page_id
    assert feedback_request.feedback_type == "useful"
    assert feedback_request.rating == 5


def test_tutor_agent_formats_graph_context() -> None:
    agent = TutorAgent(db=None)  # type: ignore[arg-type]
    text = agent._format_graph_context(
        {
            "seed_nodes": ["栈", "队列"],
            "expanded_nodes": ["BFS"],
            "relation_paths": [{"type": "prerequisite", "evidence": "先修关系"}],
        }
    )
    assert "栈" in text
    assert "BFS" in text
    assert "prerequisite" in text


def test_tutor_agent_builds_wiki_related_points() -> None:
    agent = TutorAgent(db=None)  # type: ignore[arg-type]
    knowledge_id = uuid4()
    wiki_page = SimpleNamespace(id=uuid4(), knowledge_id=knowledge_id, title="递归调用栈")

    related = agent._related_knowledge_points("Why is recursion related to stack?", [wiki_page])

    assert related[0]["name"] == "递归调用栈"
    assert related[0]["knowledge_id"] == str(knowledge_id)


def test_tutor_service_formats_citations() -> None:
    service = TutorService(db=None)  # type: ignore[arg-type]

    text = service._format_citations(
        [
            {
                "source_type": "wiki",
                "title": "递归调用栈",
                "quote": "递归调用会保存每层函数现场。",
            }
        ]
    )

    assert "[wiki] 递归调用栈" in text
    assert "递归调用会保存每层函数现场" in text


def test_simple_greeting_detection_does_not_match_course_questions() -> None:
    assert is_simple_greeting("你好") is True
    assert is_simple_greeting("嗨！") is True
    assert is_simple_greeting("你好，帮我解释一下 BFS") is False
    assert is_simple_greeting("什么是队列？") is False


def test_fast_stream_rule_review_does_not_call_review_agent() -> None:
    service = TutorService(db=None)  # type: ignore[arg-type]

    review = service._rule_review_answer(
        answer="队列遵循先进先出原则。",
        citations=[{"source_type": "document", "title": "队列"}],
    )

    assert review["pass"] is True
    assert review["reviewer"] == "fast_stream_rule"


def test_tutor_sse_uses_real_stream_events_without_calling_chat() -> None:
    asyncio.run(_test_tutor_sse_uses_real_stream_events_without_calling_chat())


async def _test_tutor_sse_uses_real_stream_events_without_calling_chat() -> None:
    class FakeStreamingService:
        chat_called = False

        async def chat(self, *args, **kwargs):
            self.chat_called = True
            raise AssertionError("streaming endpoint must not call complete chat")

        async def stream_chat(self, *args, **kwargs):
            yield {"event": "progress", "data": {"stage": "llm_generation", "message": "真实流式生成"}}
            yield {"event": "delta", "data": {"content": "第一段来自 provider"}}
            yield {"event": "done", "data": {"message_id": str(uuid4()), "citations": []}}

    service = FakeStreamingService()
    chunks = [
        chunk
        async for chunk in _stream_tutor_chat(
            service,  # type: ignore[arg-type]
            TutorChatRequest(course_id=uuid4(), question="递归为什么和栈有关？", stream=True),
            SimpleNamespace(id=uuid4(), role="student"),
        )
    ]

    assert service.chat_called is False
    assert any("第一段来自 provider" in chunk for chunk in chunks)
    assert not any('data: {"content": ""}' in chunk for chunk in chunks)
    assert chunks[-1].startswith("event: done")


def test_tutor_sse_empty_answer_emits_error_not_empty_delta() -> None:
    asyncio.run(_test_tutor_sse_empty_answer_emits_error_not_empty_delta())


async def _test_tutor_sse_empty_answer_emits_error_not_empty_delta() -> None:
    class EmptyStreamingService:
        async def stream_chat(self, *args, **kwargs):
            yield {"event": "error", "data": {"message": "Tutor 回答为空"}}

    chunks = [
        chunk
        async for chunk in _stream_tutor_chat(
            EmptyStreamingService(),  # type: ignore[arg-type]
            TutorChatRequest(course_id=uuid4(), question="递归为什么和栈有关？", stream=True),
            SimpleNamespace(id=uuid4(), role="student"),
        )
    ]

    assert chunks == [
        f"event: error\ndata: {json.dumps({'message': 'Tutor 回答为空'}, ensure_ascii=False)}\n\n"
    ]
