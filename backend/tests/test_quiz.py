"""Phase 15 tests: quiz schemas, QuizAgent parsing, and Mock Provider output."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agents.quiz_agent import QuizAgent
from app.llm.adapters.mock_provider import MockLLMProvider
from app.llm.schemas import ChatMessage
from app.schemas.quiz import QuizGenerateRequest, QuizSubmitRequest
from app.services.quiz_service import QuizService


def test_quiz_generate_request_defaults() -> None:
    course_id = uuid4()
    request = QuizGenerateRequest(course_id=course_id)

    assert request.course_id == course_id
    assert request.quiz_type == "practice"
    assert request.question_types == ["single_choice"]
    assert request.difficulty == "medium"
    assert request.count == 5


def test_quiz_generate_request_rejects_invalid_question_type() -> None:
    with pytest.raises(Exception):
        QuizGenerateRequest(course_id=uuid4(), question_types=["unsupported"])


def test_quiz_submit_request_requires_answers() -> None:
    with pytest.raises(Exception):
        QuizSubmitRequest(answers=[])


def test_quiz_agent_parses_fenced_json_and_fills_count() -> None:
    agent = QuizAgent.__new__(QuizAgent)
    content = """```json
{
  "questions": [
    {
      "question_type": "single_choice",
      "question_text": "栈的插入删除发生在哪一端？",
      "options": {"A": "队头", "B": "栈顶"},
      "standard_answer": "B",
      "analysis": "栈只能在栈顶操作。",
      "error_tags": ["概念混淆"]
    }
  ]
}
```"""

    questions = agent._parse_questions(
        content,
        knowledge_name="栈",
        question_types=["single_choice"],
        difficulty="easy",
        count=2,
    )

    assert len(questions) == 2
    assert questions[0]["standard_answer"] == "B"
    assert questions[1]["created_by"] == "system"


def test_quiz_service_normalizes_agent_questions() -> None:
    service = QuizService.__new__(QuizService)
    items = service._normalize_agent_questions(
        [{"question_text": "队列遵循什么原则？", "correct_answer": "先进先出"}],
        topic="队列",
        count=2,
        question_types=["short_answer"],
        difficulty="medium",
    )

    assert len(items) == 2
    assert items[0]["standard_answer"] == "先进先出"
    assert items[1]["question_type"] == "short_answer"


def test_quiz_service_grades_objective_answers() -> None:
    service = QuizService.__new__(QuizService)
    question = SimpleNamespace(question_type="single_choice", standard_answer="B")

    assert service._is_correct(question, " b ") is True
    assert service._is_correct(question, "A") is False


def test_mock_provider_returns_structured_quiz_json() -> None:
    asyncio.run(_test_mock_provider_returns_structured_quiz_json())


async def _test_mock_provider_returns_structured_quiz_json() -> None:
    provider = MockLLMProvider()
    response = await provider.chat([
        ChatMessage(
            role="user",
            content="你是数据结构课程的 Quiz Agent。请生成结构化练习题。知识点：栈与队列\n数量：3\nerror_tags",
        )
    ])

    payload = json.loads(response.content)
    assert len(payload["questions"]) == 3
    assert payload["questions"][0]["standard_answer"] == "B"
    assert payload["questions"][0]["error_tags"]
