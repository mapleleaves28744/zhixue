"""Phase 14 tests: tutor schemas and formatting helpers."""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.agents.tutor_agent import TutorAgent
from app.schemas.tutor import (
    TutorChatRequest,
    TutorChatResponse,
    TutorFeedbackRequest,
    TutorSaveToWikiRequest,
)
from app.services.tutor_service import TutorService


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


def test_tutor_agent_builds_wiki_related_points() -> None:
    agent = TutorAgent(db=None)  # type: ignore[arg-type]
    wiki_page = SimpleNamespace(id=uuid4(), title="递归调用栈")

    related = agent._related_knowledge_points("Why is recursion related to stack?", [wiki_page])

    assert related[0]["name"] == "递归调用栈"


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
