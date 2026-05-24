"""Phase 13 tests: resource schemas, ResourceAgent, and ResourceService helpers."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agents.context import AgentContext, AgentResult
from app.core.exceptions import BusinessException
from app.schemas.resource import (
    RESOURCE_TYPE_ALIASES,
    VALID_RESOURCE_TYPES,
    GeneratedResourceRead,
    ResourceGenerateRequest,
    ResourceGenerateResponse,
    ResourceSaveToWikiRequest,
)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestResourceSchemas:
    def test_generate_request_defaults(self) -> None:
        req = ResourceGenerateRequest(
            course_id=uuid4(),
            resource_type="explanation",
        )
        assert req.requirement is None
        assert req.use_profile is True
        assert req.save_to_wiki is False
        assert req.knowledge_id is None
        assert req.wiki_page_id is None

    def test_generate_request_with_all_fields(self) -> None:
        cid = uuid4()
        kid = uuid4()
        wid = uuid4()
        req = ResourceGenerateRequest(
            course_id=cid,
            knowledge_id=kid,
            wiki_page_id=wid,
            resource_type="summary",
            requirement="用简单语言解释",
            use_profile=False,
            save_to_wiki=True,
        )
        assert req.course_id == cid
        assert req.knowledge_id == kid
        assert req.wiki_page_id == wid
        assert req.resource_type == "summary"
        assert req.requirement == "用简单语言解释"

    def test_save_to_wiki_request_defaults(self) -> None:
        req = ResourceSaveToWikiRequest()
        assert req.wiki_page_id is None
        assert req.section_title is None

    def test_generated_resource_read_from_attributes(self) -> None:
        now = datetime.now(UTC)
        obj = SimpleNamespace(
            id=uuid4(),
            user_id=uuid4(),
            course_id=uuid4(),
            knowledge_id=uuid4(),
            wiki_page_id=None,
            resource_type="explanation",
            title="栈讲解",
            content="栈是后进先出...",
            citations=[{"source_type": "wiki", "title": "栈"}],
            personalized_reason="基于薄弱点",
            model_name="mock",
            prompt_version_id=None,
            status="active",
            created_at=now,
        )
        read = GeneratedResourceRead.model_validate(obj)
        assert read.title == "栈讲解"
        assert read.resource_type == "explanation"
        assert len(read.citations) == 1

    def test_resource_generate_response(self) -> None:
        resp = ResourceGenerateResponse(
            resource_id=uuid4(),
            title="测试资源",
            content="内容",
            citations=[],
            personalized_reason="原因",
            status="active",
        )
        assert resp.title == "测试资源"
        assert resp.status == "active"


# ---------------------------------------------------------------------------
# Resource type aliases and validation
# ---------------------------------------------------------------------------

class TestResourceTypeValidation:
    def test_chinese_aliases_map_correctly(self) -> None:
        assert RESOURCE_TYPE_ALIASES["讲解"] == "explanation"
        assert RESOURCE_TYPE_ALIASES["总结"] == "summary"
        assert RESOURCE_TYPE_ALIASES["例题"] == "example"
        assert RESOURCE_TYPE_ALIASES["复习卡"] == "flashcard"
        assert RESOURCE_TYPE_ALIASES["错题解析"] == "review"

    def test_english_aliases_map_correctly(self) -> None:
        assert RESOURCE_TYPE_ALIASES["explain"] == "explanation"
        assert RESOURCE_TYPE_ALIASES["note"] == "summary"

    def test_valid_resource_types_complete(self) -> None:
        expected = {"explanation", "summary", "example", "flashcard", "review"}
        assert VALID_RESOURCE_TYPES == expected

    def test_normalize_resource_type_in_service(self) -> None:
        from app.services.resource_service import ResourceService

        svc = ResourceService.__new__(ResourceService)
        assert svc._normalize_resource_type("讲解") == "explanation"
        assert svc._normalize_resource_type("explanation") == "explanation"
        assert svc._normalize_resource_type("EXPLANATION") == "explanation"
        assert svc._normalize_resource_type("  summary  ") == "summary"

    def test_normalize_resource_type_rejects_invalid(self) -> None:
        from app.services.resource_service import ResourceService

        svc = ResourceService.__new__(ResourceService)
        with pytest.raises(BusinessException):
            svc._normalize_resource_type("invalid_type")


# ---------------------------------------------------------------------------
# ResourceAgent rule-based logic
# ---------------------------------------------------------------------------

class TestResourceAgentHelpers:
    def test_extract_title_from_markdown_heading(self) -> None:
        from app.agents.resource_agent import ResourceAgent

        agent = ResourceAgent.__new__(ResourceAgent)
        content = "# 栈与队列讲解\n\n栈是后进先出..."
        title = agent._extract_title(content, resource_type="explanation", knowledge_name="栈与队列")
        assert title == "栈与队列讲解"

    def test_extract_title_fallback(self) -> None:
        from app.agents.resource_agent import ResourceAgent

        agent = ResourceAgent.__new__(ResourceAgent)
        content = "没有标题的内容"
        title = agent._extract_title(content, resource_type="summary", knowledge_name="图")
        assert "图" in title
        assert "总结" in title

    def test_build_citations_with_wiki_and_rag(self) -> None:
        from app.agents.resource_agent import ResourceAgent

        agent = ResourceAgent.__new__(ResourceAgent)
        wiki = SimpleNamespace(id=uuid4(), title="栈Wiki")
        rag_result = SimpleNamespace(
            material_id=uuid4(),
            chunk_id=uuid4(),
            source_title="教材第3章",
            page_no=15,
            score=0.92,
            content="栈是一种受限线性表...",
        )
        citations = agent._build_citations(wiki, [rag_result])
        assert len(citations) == 2
        assert citations[0]["source_type"] == "wiki"
        assert citations[1]["source_type"] == "document"
        assert citations[1]["score"] == 0.92

    def test_build_citations_empty_falls_back_to_inference(self) -> None:
        from app.agents.resource_agent import ResourceAgent

        agent = ResourceAgent.__new__(ResourceAgent)
        citations = agent._build_citations(None, [])
        assert len(citations) == 1
        assert citations[0]["source_type"] == "inference"

    def test_build_personalized_reason_with_requirement(self) -> None:
        from app.agents.resource_agent import ResourceAgent

        agent = ResourceAgent.__new__(ResourceAgent)
        reason = agent._build_personalized_reason(
            resource_type="explanation",
            knowledge_name="栈",
            profile_text="一般状态",
            requirement="用通俗语言解释",
        )
        assert "通俗语言解释" in reason

    def test_build_personalized_reason_with_weak_points(self) -> None:
        from app.agents.resource_agent import ResourceAgent

        agent = ResourceAgent.__new__(ResourceAgent)
        reason = agent._build_personalized_reason(
            resource_type="summary",
            knowledge_name="二叉树",
            profile_text="薄弱点：树结构",
            requirement="",
        )
        assert "薄弱点" in reason

    def test_build_personalized_reason_default(self) -> None:
        from app.agents.resource_agent import ResourceAgent

        agent = ResourceAgent.__new__(ResourceAgent)
        reason = agent._build_personalized_reason(
            resource_type="example",
            knowledge_name="图",
            profile_text="一般状态",
            requirement="",
        )
        assert "图" in reason


# ---------------------------------------------------------------------------
# ResourceAgent run (with mocked LLM and DB)
# ---------------------------------------------------------------------------

class FakePromptServiceForResource:
    async def render_prompt(self, **kwargs):
        return SimpleNamespace(
            content="请为学生生成个性化学习资源",
            prompt_version_id=None,
        )


class FakeLLMResponseForResource:
    content = "# 栈与队列讲解\n\n栈是后进先出的线性结构。\n\n## 个性化原因\n\n基于学生画像生成。\n\n## 引用来源\n\n- 教材第3章"
    model = "mock"
    total_tokens = 200


class FakeLLMForResource:
    async def chat(self, messages, **kwargs):
        return FakeLLMResponseForResource()


class FakeRetriever:
    async def search(self, **kwargs):
        return []


class FakeProfileService:
    async def get_profile(self, user_id):
        return None


class FakeMemoryService:
    async def list_memories(self, user_id, course_id):
        return []


class FakeDBForResourceAgent:
    async def execute(self, stmt):
        return SimpleNamespace(scalar_one_or_none=lambda: None)


def test_resource_agent_run_with_mock_llm() -> None:
    asyncio.run(_test_resource_agent_run_with_mock_llm())


async def _test_resource_agent_run_with_mock_llm() -> None:
    from unittest.mock import patch

    from app.agents.resource_agent import ResourceAgent

    agent = ResourceAgent(db=FakeDBForResourceAgent())  # type: ignore[arg-type]
    context = AgentContext(
        user_id=uuid4(),
        course_id=uuid4(),
        task_type="generate_resource",
        params={
            "resource_type": "explanation",
            "knowledge_id": None,
            "wiki_page_id": None,
            "knowledge_name": "栈与队列",
            "requirement": "",
            "use_profile": True,
        },
    )

    with (
        patch("app.agents.resource_agent.PromptService", return_value=FakePromptServiceForResource()),
        patch("app.agents.resource_agent.get_llm_provider", return_value=FakeLLMForResource()),
        patch("app.agents.resource_agent.VectorRetriever", return_value=FakeRetriever()),
        patch("app.agents.resource_agent.ProfileService", return_value=FakeProfileService()),
        patch("app.agents.resource_agent.MemoryService", return_value=FakeMemoryService()),
    ):
        result = await agent.run(context)

    assert result.success is True
    assert "content" in result.data
    assert "citations" in result.data
    assert "personalized_reason" in result.data
    assert "title" in result.data
    assert result.data["resource_type"] == "explanation"


def test_resource_agent_invalid_type_returns_error() -> None:
    asyncio.run(_test_resource_agent_invalid_type_returns_error())


async def _test_resource_agent_invalid_type_returns_error() -> None:
    from app.agents.resource_agent import ResourceAgent

    agent = ResourceAgent(db=FakeDBForResourceAgent())  # type: ignore[arg-type]
    context = AgentContext(
        user_id=uuid4(),
        course_id=uuid4(),
        task_type="generate_resource",
        params={"resource_type": "invalid_type"},
    )
    result = await agent.run(context)
    assert result.success is False
    assert "不支持" in result.message


# ---------------------------------------------------------------------------
# ResourceService helper methods
# ---------------------------------------------------------------------------

class TestResourceServiceHelpers:
    def test_default_title_with_knowledge(self) -> None:
        from app.services.resource_service import ResourceService

        svc = ResourceService.__new__(ResourceService)
        knowledge = SimpleNamespace(name="栈")
        title = svc._default_title("explanation", knowledge, None)
        assert title == "栈讲解"

    def test_default_title_with_wiki(self) -> None:
        from app.services.resource_service import ResourceService

        svc = ResourceService.__new__(ResourceService)
        wiki = SimpleNamespace(title="二叉树Wiki")
        title = svc._default_title("summary", None, wiki)
        assert title == "二叉树Wiki总结"

    def test_default_title_fallback(self) -> None:
        from app.services.resource_service import ResourceService

        svc = ResourceService.__new__(ResourceService)
        title = svc._default_title("example", None, None)
        assert title == "数据结构例题"

    def test_ensure_list_with_list(self) -> None:
        from app.services.resource_service import ResourceService

        svc = ResourceService.__new__(ResourceService)
        assert svc._ensure_list([1, 2]) == [1, 2]

    def test_ensure_list_with_non_list(self) -> None:
        from app.services.resource_service import ResourceService

        svc = ResourceService.__new__(ResourceService)
        assert svc._ensure_list(None) == []
        assert svc._ensure_list("string") == []

    def test_uuid_parsing(self) -> None:
        from app.services.resource_service import ResourceService

        svc = ResourceService.__new__(ResourceService)
        uid = uuid4()
        assert svc._uuid(uid) == uid
        assert svc._uuid(str(uid)) == uid
        assert svc._uuid(None) is None
        assert svc._uuid("") is None
        assert svc._uuid("not-a-uuid") is None

    def test_format_resource_for_wiki(self) -> None:
        from app.services.resource_service import ResourceService

        svc = ResourceService.__new__(ResourceService)
        resource = SimpleNamespace(
            title="栈讲解",
            content="栈是后进先出...",
            citations=[
                {"source_type": "wiki", "title": "栈Wiki"},
                {"source_type": "document", "title": "教材"},
            ],
            personalized_reason="基于薄弱点生成",
        )
        formatted = svc._format_resource_for_wiki(resource, "自定义标题")
        assert "## 自定义标题" in formatted
        assert "栈是后进先出" in formatted
        assert "个性化原因" in formatted
        assert "引用来源" in formatted
        assert "栈Wiki" in formatted

    def test_format_resource_for_wiki_empty_citations(self) -> None:
        from app.services.resource_service import ResourceService

        svc = ResourceService.__new__(ResourceService)
        resource = SimpleNamespace(
            title="测试",
            content="内容",
            citations=[],
            personalized_reason=None,
        )
        formatted = svc._format_resource_for_wiki(resource, "标题")
        assert "AI 推断内容" in formatted
        assert "暂无个性化证据" in formatted
