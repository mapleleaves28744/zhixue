from __future__ import annotations

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.agent_runtime import supervisor_intents
from app.schemas.tutor import TutorChatRequest, TutorCitation
from app.services.conversation_context_service import ConversationContext
from app.services.prompt_service import RenderedPrompt
from app.services.tutor_service import TutorService
from app.services.web_search_service import WebSearchService


def test_web_search_intent_detects_online_search_phrases() -> None:
    assert supervisor_intents.web_search_intent("联网搜索 Python 3.14 新特性")
    assert supervisor_intents.web_search_intent("帮我查一下网上最新的 AI 新闻")
    assert not supervisor_intents.web_search_intent("基于课程资料解释二叉树")
    assert not supervisor_intents.web_search_intent("检索课程知识库中的哈希表")


def test_plan_required_tools_prioritizes_search_web() -> None:
    tools = supervisor_intents.plan_required_tools("联网搜索 Rust 异步运行时对比", is_profile_update_only=False)
    assert tools[0] == "search_web"


def test_parse_markdown_results() -> None:
    service = WebSearchService(api_key="")
    raw = """## Search Results (2 results, 100ms)

### 1. Example Title
- **URL**: https://example.com/a
- This is a short summary about the topic.

### 2. Another Title
- **URL**: https://example.com/b
- Another summary line.
"""
    items = service._parse_markdown_results(raw)
    assert len(items) == 2
    assert items[0]["title"] == "Example Title"
    assert items[0]["url"] == "https://example.com/a"
    assert "summary" in items[0]["snippet"]


@pytest.mark.asyncio
async def test_search_returns_mock_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.web_search_service.settings.anysearch_enabled", True)
    monkeypatch.setattr("app.services.web_search_service.settings.anysearch_api_key", "")
    service = WebSearchService()
    payload = await service.search(query="测试联网搜索")
    assert payload["provider"] == "mock"
    assert payload["items"]


def test_supervisor_formats_search_web_answer_for_chat() -> None:
    from app.agent_runtime.supervisor import MiMoSupervisor

    supervisor = MiMoSupervisor(provider=object())  # type: ignore[arg-type]
    state = {
        "goal": "联网搜索 Python 3.14 有哪些新特性",
        "observations": [
            {
                "success": True,
                "tool_name": "search_web",
                "output": {
                    "query": "Python 3.14 新特性",
                    "provider": "anysearch",
                    "items": [
                        {
                            "title": "What’s new in Python 3.14",
                            "url": "https://docs.python.org/3/whatsnew/3.14.html",
                            "snippet": "This article explains the new features in Python 3.14.",
                        }
                    ],
                },
            }
        ],
    }
    answer = supervisor._build_completion_answer(state)
    assert "联网搜索" in answer
    assert "What’s new in Python 3.14" in answer
    assert "docs.python.org" in answer
    assert "所需学习内容已生成" not in answer


@pytest.mark.asyncio
async def test_web_followup_reads_the_cited_page_before_summarizing(monkeypatch) -> None:
    course_id, user_id = uuid4(), uuid4()
    context = ConversationContext(web_references=(
        {"title": "第一项", "url": "https://example.com/one", "source_message_id": "m1"},
        {"title": "第二项", "url": "https://example.com/two", "source_message_id": "m1"},
    ))
    extracted = AsyncMock(return_value={"provider": "anysearch", "content": "第二项正文：介绍栈的应用。"})
    render = AsyncMock(return_value=RenderedPrompt(content="根据第二项正文总结", prompt_version_id=None))
    provider = SimpleNamespace(chat=AsyncMock(return_value=SimpleNamespace(
        content="第二项主要介绍栈的应用。", provider="test-llm",
    )))
    monkeypatch.setattr("app.services.web_search_service.WebSearchService.extract_page", extracted)
    monkeypatch.setattr("app.services.prompt_service.PromptService.render_prompt", render)
    monkeypatch.setattr("app.llm.provider.get_llm_provider", lambda **kwargs: provider)
    monkeypatch.setattr("app.core.config.settings.llm_provider", "openai_compatible")
    monkeypatch.setattr("app.core.config.settings.llm_api_key", "test-only")
    service = TutorService(SimpleNamespace())  # type: ignore[arg-type]

    answer, citations, provider_name = await service._answer_web_reference(
        context=context,
        payload=TutorChatRequest(course_id=course_id, question="总结第二个链接"),
        current_user=SimpleNamespace(id=user_id),
        course=SimpleNamespace(id=course_id),
    )

    extracted.assert_awaited_once_with(url="https://example.com/two")
    assert answer == "第二项主要介绍栈的应用。"
    assert citations[0]["url"] == "https://example.com/two"
    assert TutorCitation.model_validate(citations[0]).model_dump()["url"] == citations[0]["url"]
    assert provider_name == "test-llm"


@pytest.mark.asyncio
async def test_web_followup_without_cited_target_does_not_fetch_or_invent(monkeypatch) -> None:
    extracted = AsyncMock()
    monkeypatch.setattr("app.services.web_search_service.WebSearchService.extract_page", extracted)
    course_id = uuid4()
    service = TutorService(SimpleNamespace())  # type: ignore[arg-type]

    answer, citations, provider_name = await service._answer_web_reference(
        context=ConversationContext(),
        payload=TutorChatRequest(course_id=course_id, question="总结第二个链接"),
        current_user=SimpleNamespace(id=uuid4()),
        course=SimpleNamespace(id=course_id),
    )

    assert "无法确定" in answer
    assert citations == []
    assert provider_name == "rule"
    extracted.assert_not_awaited()


@pytest.mark.asyncio
async def test_web_followup_mock_mode_returns_labeled_excerpt(monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.settings.llm_provider", "mock")
    monkeypatch.setattr("app.services.web_search_service.WebSearchService.extract_page", AsyncMock(
        return_value={"provider": "anysearch", "content": "可以核对的网页正文"},
    ))
    course_id = uuid4()
    service = TutorService(SimpleNamespace())  # type: ignore[arg-type]
    answer, citations, provider_name = await service._answer_web_reference(
        context=ConversationContext(web_references=(
            {"title": "示例网页", "url": "https://example.com/page", "source_message_id": "m1"},
        )),
        payload=TutorChatRequest(course_id=course_id, question="总结第一个链接"),
        current_user=SimpleNamespace(id=uuid4()), course=SimpleNamespace(id=course_id),
    )

    assert "Mock 模式未生成 AI 摘要" in answer
    assert "可以核对的网页正文" in answer
    assert citations[0]["url"] == "https://example.com/page"
    assert provider_name == "extractive"


@pytest.mark.asyncio
async def test_quiz_option_followup_reads_owned_single_question(monkeypatch) -> None:
    course_id, user_id, quiz_id, question_id = uuid4(), uuid4(), uuid4(), uuid4()
    load_quiz = AsyncMock(return_value=SimpleNamespace(
        id=quiz_id, course_id=course_id, title="栈练习", questions=[SimpleNamespace(
            id=question_id, question_text="栈的出入顺序是什么？",
            options={"A": "先进先出", "B": "后进先出"},
            standard_answer="B", analysis="栈遵循后进先出。",
        )],
    ))
    monkeypatch.setattr("app.repositories.quiz_repository.QuizRepository.get_quiz_for_user", load_quiz)
    monkeypatch.setattr("app.core.config.settings.llm_provider", "mock")
    service = TutorService(SimpleNamespace())  # type: ignore[arg-type]

    answer, citations, provider_name = await service._answer_quiz_option(
        context=ConversationContext(quiz_reference={"id": str(quiz_id), "source_message_id": "m1"}),
        payload=TutorChatRequest(course_id=course_id, question="讲解上一题第二个选项"),
        current_user=SimpleNamespace(id=user_id), course=SimpleNamespace(id=course_id),
    )

    load_quiz.assert_awaited_once_with(quiz_id=quiz_id, user_id=user_id)
    assert "B：后进先出" in answer
    assert citations[0]["source_id"] == str(question_id)
    assert provider_name == "extractive"


@pytest.mark.asyncio
async def test_quiz_option_followup_does_not_guess_multi_question_target(monkeypatch) -> None:
    course_id, quiz_id = uuid4(), uuid4()
    load_quiz = AsyncMock(return_value=SimpleNamespace(
        course_id=course_id, questions=[SimpleNamespace(), SimpleNamespace()],
    ))
    monkeypatch.setattr("app.repositories.quiz_repository.QuizRepository.get_quiz_for_user", load_quiz)
    service = TutorService(SimpleNamespace())  # type: ignore[arg-type]

    answer, citations, provider_name = await service._answer_quiz_option(
        context=ConversationContext(quiz_reference={"id": str(quiz_id), "source_message_id": "m1"}),
        payload=TutorChatRequest(course_id=course_id, question="讲解上一题第二个选项"),
        current_user=SimpleNamespace(id=uuid4()), course=SimpleNamespace(id=course_id),
    )

    assert "多道题" in answer
    assert citations == []
    assert provider_name == "rule"


@pytest.mark.asyncio
async def test_material_followup_reads_verified_cited_chunk(monkeypatch) -> None:
    course_id, user_id, material_id, chunk_id = uuid4(), uuid4(), uuid4(), uuid4()
    read_material = AsyncMock(return_value=SimpleNamespace(
        id=material_id, course_id=course_id, file_name="栈讲义.pdf",
    ))
    read_chunk = AsyncMock(return_value=SimpleNamespace(
        id=chunk_id, material_id=material_id, course_id=course_id,
        page_no=3, content="栈遵循后进先出。",
    ))
    preview = AsyncMock()
    monkeypatch.setattr("app.services.material_service.MaterialService.get_readable_material", read_material)
    monkeypatch.setattr("app.repositories.chunk_repository.ChunkRepository.get_by_id", read_chunk)
    monkeypatch.setattr("app.repositories.chunk_repository.ChunkRepository.list_preview_by_material", preview)
    monkeypatch.setattr("app.core.config.settings.llm_provider", "mock")
    service = TutorService(SimpleNamespace())  # type: ignore[arg-type]

    answer, citations, provider_name = await service._answer_material_reference(
        context=ConversationContext(material_references=({
            "id": str(material_id), "chunk_ids": [str(chunk_id)], "source_message_id": "m1",
        },)),
        payload=TutorChatRequest(course_id=course_id, question="解释刚才那份资料引用的片段"),
        current_user=SimpleNamespace(id=user_id), course=SimpleNamespace(id=course_id),
    )

    read_material.assert_awaited_once_with(material_id, SimpleNamespace(id=user_id))
    preview.assert_not_awaited()
    assert "只覆盖上次回答引用的片段" in answer
    assert "栈遵循后进先出" in answer
    assert citations[0]["chunk_id"] == str(chunk_id)
    assert provider_name == "extractive"


@pytest.mark.asyncio
async def test_material_followup_asks_when_multiple_documents_were_cited(monkeypatch) -> None:
    read_material = AsyncMock()
    monkeypatch.setattr("app.services.material_service.MaterialService.get_readable_material", read_material)
    course_id = uuid4()
    service = TutorService(SimpleNamespace())  # type: ignore[arg-type]

    answer, citations, provider_name = await service._answer_material_reference(
        context=ConversationContext(material_references=(
            {"id": str(uuid4()), "chunk_ids": []},
            {"id": str(uuid4()), "chunk_ids": []},
        )),
        payload=TutorChatRequest(course_id=course_id, question="总结刚才那份资料"),
        current_user=SimpleNamespace(id=uuid4()), course=SimpleNamespace(id=course_id),
    )

    assert "多份资料" in answer
    assert citations == []
    assert provider_name == "rule"
    read_material.assert_not_awaited()
