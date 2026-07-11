"""Phase 14 tests: tutor schemas and formatting helpers."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.tutor import _stream_tutor_chat
from app.agents.tutor_agent import TutorAgent
from app.agents.context import AgentContext
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


@pytest.mark.asyncio
async def test_tutor_agent_run_delegates_to_grounded_pipeline(monkeypatch) -> None:
    user_id = uuid4()
    course_id = uuid4()
    run_id = uuid4()
    user = SimpleNamespace(id=user_id, role="student")
    response = TutorChatResponse(
        answer="栈遵循后进先出。",
        provider="mock",
        citations=[
            {
                "citation_key": "S1",
                "source_type": "document",
                "title": "栈讲义",
            }
        ],
    )
    answer = AsyncMock(return_value=response)

    class FakePipeline:
        def __init__(self, db: object) -> None:
            self.db = db

        async def answer(
            self,
            payload: TutorChatRequest,
            current_user: object,
            *,
            agent_run_id=None,
        ):
            return await answer(
                payload,
                current_user,
                agent_run_id=agent_run_id,
            )

    class FakeResult:
        def scalar_one(self) -> object:
            return user

    class FakeDB:
        async def execute(self, statement: object) -> FakeResult:
            return FakeResult()

    import app.services.grounded_qa_pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "GroundedQaPipeline", FakePipeline)
    result = await TutorAgent(FakeDB()).run(  # type: ignore[arg-type]
        AgentContext(
            user_id=user_id,
            course_id=course_id,
            task_type="course_qa",
            params={"question": "什么是栈？"},
            run_id=run_id,
        )
    )

    assert result.success is True
    delegated_payload, delegated_user = answer.await_args.args
    assert delegated_payload.course_id == course_id
    assert delegated_payload.question == "什么是栈？"
    assert delegated_user is user
    assert answer.await_args.kwargs["agent_run_id"] == run_id
    assert all(isinstance(item, str) for item in result.evidence)
    assert "S1" in result.evidence[0]
    assert "栈讲义" in result.evidence[0]


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


@pytest.mark.asyncio
async def test_tutor_service_chat_and_stream_are_thin_pipeline_delegates(
    monkeypatch,
) -> None:
    expected = TutorChatResponse(answer="来自统一管线")
    answer = AsyncMock(return_value=expected)
    stream_calls: list[tuple[object, object]] = []

    class FakePipeline:
        def __init__(self, db: object) -> None:
            self.db = db

        async def answer(self, payload, current_user):
            return await answer(payload, current_user)

        async def stream(self, payload, current_user):
            stream_calls.append((payload, current_user))
            async for event in _async_events(
                [
                    {"event": "delta", "data": {"content": "流式"}},
                    {"event": "done", "data": expected.model_dump(mode="json")},
                ]
            ):
                yield event

    import app.services.tutor_service as tutor_module

    monkeypatch.setattr(tutor_module, "GroundedQaPipeline", FakePipeline, raising=False)
    service = TutorService(db=SimpleNamespace())  # type: ignore[arg-type]
    payload = TutorChatRequest(course_id=uuid4(), question="什么是栈？")
    user = SimpleNamespace(id=uuid4(), role="student")

    assert await service.chat(payload=payload, current_user=user) is expected
    events = [event async for event in service.stream_chat(payload=payload, current_user=user)]

    answer.assert_awaited_once_with(payload, user)
    assert stream_calls == [(payload, user)]
    assert [event["event"] for event in events] == ["delta", "done"]


async def _async_events(events):
    for event in events:
        yield event


@pytest.mark.asyncio
async def test_publish_chat_completed_enqueues_validated_citations(monkeypatch) -> None:
    from app.services import chat_knowledge_pipeline as module

    bus = SimpleNamespace(publish=AsyncMock())
    monkeypatch.setattr("app.core.event_bus.get_event_bus", lambda: bus)
    citations = [{"citation_key": "S1", "source_type": "document", "title": "栈讲义"}]

    published = await module.publish_chat_completed(
        user_id=uuid4(),
        course_id=uuid4(),
        question="什么是栈？",
        answer="后进先出 [S1]。",
        citations=citations,
    )

    data = bus.publish.await_args.args[1]
    assert data["citations"] == citations
    assert published is True


@pytest.mark.asyncio
async def test_publish_chat_completed_reports_enqueue_failure(monkeypatch) -> None:
    from app.services import chat_knowledge_pipeline as module

    bus = SimpleNamespace(publish=AsyncMock(side_effect=RuntimeError("queue unavailable")))
    monkeypatch.setattr("app.core.event_bus.get_event_bus", lambda: bus)

    published = await module.publish_chat_completed(
        user_id=uuid4(),
        course_id=uuid4(),
        question="什么是栈？",
        answer="后进先出。",
    )

    assert published is False


@pytest.mark.asyncio
async def test_event_bus_publish_only_enqueues_without_waiting_for_handler() -> None:
    from app.core.event_bus import EventBus

    bus = EventBus()
    handler_called = asyncio.Event()

    async def slow_handler(event):
        handler_called.set()
        await asyncio.sleep(10)

    bus.subscribe("chat_completed", slow_handler)

    event = await asyncio.wait_for(
        bus.publish("chat_completed", {"answer": "完成"}), timeout=0.1
    )

    assert event.event_type == "chat_completed"
    assert bus._queue.qsize() == 1
    assert handler_called.is_set() is False


@pytest.mark.asyncio
async def test_tutor_postprocess_runs_review_and_memory_before_commit(monkeypatch) -> None:
    from app.core.event_bus import Event
    from app.services.agent_service import AgentService
    from app.services.memory_service import MemoryService
    from app.services.tutor_postprocess_service import TutorPostprocessService

    review = AsyncMock(return_value=SimpleNamespace(success=True))
    reflect = AsyncMock(return_value=[])
    monkeypatch.setattr(AgentService, "run_task", review)
    monkeypatch.setattr(MemoryService, "reflect", reflect)
    db = SimpleNamespace(commit=AsyncMock())
    user_id = uuid4()
    course_id = uuid4()

    await TutorPostprocessService(db).run(  # type: ignore[arg-type]
        Event(
            event_type="chat_completed",
            data={
                "user_id": user_id,
                "course_id": course_id,
                "answer": "后进先出 [S1]。",
                "citations": [{"citation_key": "S1", "title": "栈讲义"}],
            },
        )
    )

    assert review.await_args.kwargs["task_type"] == "review_content"
    assert "S1" in review.await_args.kwargs["params"]["content"]
    reflect.assert_awaited_once_with(user_id, course_id)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_chat_postprocess_uses_session_independent_from_mastery(monkeypatch) -> None:
    from app.core.event_bus import Event
    from app.core.event_handlers import on_chat_completed
    from app.services.mastery_service import MasteryService
    from app.services.tutor_postprocess_service import TutorPostprocessService

    sessions = [
        SimpleNamespace(commit=AsyncMock()),
        SimpleNamespace(commit=AsyncMock()),
        SimpleNamespace(commit=AsyncMock()),
    ]
    entered: list[object] = []

    class SessionContext:
        def __init__(self, db):
            self.db = db

        async def __aenter__(self):
            entered.append(self.db)
            return self.db

        async def __aexit__(self, *args):
            return False

    def session_factory():
        return SessionContext(sessions[len(entered)])

    monkeypatch.setattr("app.db.session.AsyncSessionLocal", session_factory)
    monkeypatch.setattr(MasteryService, "sync_profile_snapshot", AsyncMock())
    monkeypatch.setattr(
        "app.services.profile_service.ProfileService.ingest_dialogue_profile",
        AsyncMock(),
    )
    postprocess_run = AsyncMock()
    monkeypatch.setattr(TutorPostprocessService, "run", postprocess_run)

    await on_chat_completed(
        Event(
            event_type="chat_completed",
            data={
                "user_id": uuid4(),
                "course_id": uuid4(),
                "question": "什么是栈？",
                "answer": "栈遵循后进先出。",
                "skip_graph_extract": True,
            },
        )
    )

    assert entered == sessions
    assert postprocess_run.await_args.args[0] is not None
    assert postprocess_run.await_args.args[0].event_type == "chat_completed"


@pytest.mark.asyncio
async def test_chat_greeting_skips_deep_postprocess_and_graph(monkeypatch) -> None:
    from app.core.event_bus import Event
    from app.core.event_handlers import on_chat_completed
    from app.services.mastery_service import MasteryService
    from app.services.tutor_postprocess_service import TutorPostprocessService

    postprocess_run = AsyncMock()
    graph_extract = AsyncMock()
    mastery_update = AsyncMock()
    monkeypatch.setattr(MasteryService, "apply_ask_update", mastery_update)
    monkeypatch.setattr(TutorPostprocessService, "run", postprocess_run)
    monkeypatch.setattr(
        "app.workers.knowledge_extract_worker.handle_chat_completed", graph_extract
    )

    await on_chat_completed(
        Event(
            event_type="chat_completed",
            data={
                "user_id": uuid4(),
                "course_id": uuid4(),
                "knowledge_id": uuid4(),
                "question": "嗨！",
                "answer": "你好！",
            },
        )
    )

    postprocess_run.assert_not_awaited()
    graph_extract.assert_not_awaited()
    mastery_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_router_keeps_partial_delta_then_emits_error() -> None:
    class BrokenStreamingService:
        async def stream_chat(self, *args, **kwargs):
            yield {"event": "delta", "data": {"content": "已经生成的部分"}}
            raise RuntimeError("provider stream interrupted")

    chunks = [
        chunk
        async for chunk in _stream_tutor_chat(
            BrokenStreamingService(),  # type: ignore[arg-type]
            TutorChatRequest(course_id=uuid4(), question="什么是栈？", stream=True),
            SimpleNamespace(id=uuid4(), role="student"),
        )
    ]

    assert "已经生成的部分" in chunks[0]
    assert chunks[-1].startswith("event: error")
    assert "provider stream interrupted" in chunks[-1]
