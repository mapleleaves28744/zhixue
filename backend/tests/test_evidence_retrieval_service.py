from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.evidence_retrieval_service import EvidenceRetrievalService


@pytest.mark.asyncio
async def test_retrieval_filters_low_confidence_and_limits_two_chunks_per_material() -> None:
    material_id = uuid4()
    service = EvidenceRetrievalService(db=None)  # type: ignore[arg-type]
    service.graph.search = AsyncMock(
        return_value={
            "items": [
                {
                    "chunk_id": str(uuid4()),
                    "material_id": str(material_id),
                    "content": "栈是 LIFO",
                    "source_title": "讲义",
                    "vector_score": 0.61,
                    "keyword_score": 0.0,
                    "score": 0.61,
                    "retrieval_mode": "vector",
                    "extra_meta": {},
                },
                {
                    "chunk_id": str(uuid4()),
                    "material_id": str(material_id),
                    "content": "入栈操作",
                    "source_title": "讲义",
                    "vector_score": 0.58,
                    "keyword_score": 0.0,
                    "score": 0.58,
                    "retrieval_mode": "vector",
                    "extra_meta": {},
                },
                {
                    "chunk_id": str(uuid4()),
                    "material_id": str(material_id),
                    "content": "出栈操作",
                    "source_title": "讲义",
                    "vector_score": 0.57,
                    "keyword_score": 0.0,
                    "score": 0.57,
                    "retrieval_mode": "vector",
                    "extra_meta": {},
                },
                {
                    "chunk_id": str(uuid4()),
                    "material_id": str(uuid4()),
                    "content": "无关内容",
                    "source_title": "干扰资料",
                    "vector_score": 0.12,
                    "keyword_score": 0.0,
                    "score": 0.12,
                    "retrieval_mode": "vector",
                    "extra_meta": {},
                },
            ],
            "graph_context": {
                "seed_knowledge_ids": [],
                "expanded_knowledge_ids": [],
                "relation_paths": [],
            },
        }
    )
    service._load_wiki_pages = AsyncMock(return_value=[])

    bundle = await service.retrieve(
        course_id=uuid4(),
        user_id=uuid4(),
        question="什么是栈？",
        top_k=5,
        knowledge_id=None,
        wiki_page_id=None,
        use_rag=True,
        use_wiki=True,
    )

    assert len(bundle.evidence) == 2
    assert {item.source_id for item in bundle.evidence} == {material_id}
    assert [item.citation_key for item in bundle.evidence] == ["S1", "S2"]
    assert bundle.candidate_count == 4


@pytest.mark.asyncio
async def test_retrieval_rejects_document_candidates_without_real_identifiers() -> None:
    service = EvidenceRetrievalService(db=None)  # type: ignore[arg-type]
    service.graph.search = AsyncMock(
        return_value={
            "items": [
                {
                    "chunk_id": "synthetic",
                    "material_id": str(uuid4()),
                    "content": "看似相关但没有真实片段 ID",
                    "source_title": "讲义",
                    "vector_score": 0.9,
                    "keyword_score": 0.0,
                    "score": 0.9,
                    "retrieval_mode": "vector",
                    "extra_meta": {},
                }
            ],
            "graph_context": {},
        }
    )
    service._load_wiki_pages = AsyncMock(return_value=[])

    bundle = await service.retrieve(
        course_id=uuid4(),
        user_id=uuid4(),
        question="什么是栈？",
        top_k=5,
        knowledge_id=None,
        wiki_page_id=None,
        use_rag=True,
        use_wiki=False,
    )

    assert bundle.evidence == []
    assert bundle.candidate_count == 1


@pytest.mark.asyncio
async def test_explicit_wiki_is_strong_and_auto_matched_wiki_is_acceptable() -> None:
    explicit_id = uuid4()
    knowledge_id = uuid4()
    explicit = SimpleNamespace(
        id=explicit_id,
        knowledge_id=knowledge_id,
        title="递归调用栈",
        summary="显式选择的页面",
        content="递归调用会保存现场。",
    )
    automatic = SimpleNamespace(
        id=uuid4(),
        knowledge_id=knowledge_id,
        title="栈结构",
        summary="自动匹配的页面",
        content="栈是后进先出结构。",
    )
    service = EvidenceRetrievalService(db=None)  # type: ignore[arg-type]
    service._load_wiki_pages = AsyncMock(side_effect=[[explicit], [automatic]])

    explicit_bundle = await service.retrieve(
        course_id=uuid4(), user_id=uuid4(), question="递归", top_k=5,
        knowledge_id=knowledge_id, wiki_page_id=explicit_id, use_rag=False, use_wiki=True,
    )
    automatic_bundle = await service.retrieve(
        course_id=uuid4(), user_id=uuid4(), question="栈结构", top_k=5,
        knowledge_id=knowledge_id, wiki_page_id=None, use_rag=False, use_wiki=True,
    )

    assert explicit_bundle.evidence[0].source_id == explicit_id
    assert explicit_bundle.evidence[0].knowledge_id == knowledge_id
    assert explicit_bundle.evidence[0].confidence == "strong"
    assert automatic_bundle.evidence[0].confidence == "acceptable"


def test_wiki_related_point_uses_real_knowledge_id() -> None:
    from app.agents.tutor_agent import TutorAgent

    knowledge_id = uuid4()
    page = SimpleNamespace(id=uuid4(), knowledge_id=knowledge_id, title="递归调用栈")
    related = TutorAgent(db=None)._related_knowledge_points(  # type: ignore[arg-type]
        "递归", [page]
    )
    assert related[0]["knowledge_id"] == str(knowledge_id)


@pytest.mark.asyncio
async def test_auto_wiki_matching_requires_text_and_matching_knowledge_id() -> None:
    user_id = uuid4()
    course_id = uuid4()
    knowledge_id = uuid4()
    matching = SimpleNamespace(
        id=uuid4(), course_id=course_id, owner_id=user_id, status="active",
        knowledge_id=knowledge_id, title="递归调用栈", summary="保存函数现场",
        content="递归调用栈按层保存返回地址。",
    )
    wrong_knowledge = SimpleNamespace(
        id=uuid4(), course_id=course_id, owner_id=user_id, status="active",
        knowledge_id=uuid4(), title="递归调用栈", summary="另一个知识点",
        content="递归调用栈。",
    )
    unrelated = SimpleNamespace(
        id=uuid4(), course_id=course_id, owner_id=user_id, status="active",
        knowledge_id=knowledge_id, title="冒泡排序", summary="交换相邻元素",
        content="排序算法。",
    )
    service = EvidenceRetrievalService(db=None)  # type: ignore[arg-type]
    service.courses = MagicMock()
    service.courses.get_by_id = AsyncMock(
        return_value=SimpleNamespace(
            owner_id=uuid4(), visibility="private", status="active"
        )
    )
    service.wiki = MagicMock()
    service.wiki.list_by_owners = AsyncMock(
        return_value=([wrong_knowledge, unrelated, matching], 3)
    )

    pages = await service._load_wiki_pages(
        course_id=course_id,
        user_id=user_id,
        question="递归调用栈如何保存现场？",
        knowledge_id=knowledge_id,
        wiki_page_id=None,
    )

    assert pages == [matching]
    service.wiki.list_by_owners.assert_awaited_once_with(
        [user_id], course_id, page_size=20
    )


@pytest.mark.asyncio
async def test_auto_wiki_matching_returns_empty_when_question_has_no_match() -> None:
    user_id = uuid4()
    course_id = uuid4()
    page = SimpleNamespace(
        id=uuid4(), course_id=course_id, owner_id=user_id, status="active",
        knowledge_id=uuid4(), title="冒泡排序", summary="交换相邻元素",
        content="排序算法。",
    )
    service = EvidenceRetrievalService(db=None)  # type: ignore[arg-type]
    service.courses = MagicMock()
    service.courses.get_by_id = AsyncMock(return_value=None)
    service.wiki = MagicMock()
    service.wiki.list_by_owners = AsyncMock(return_value=([page], 1))

    pages = await service._load_wiki_pages(
        course_id=course_id,
        user_id=user_id,
        question="递归调用栈如何工作？",
        knowledge_id=None,
        wiki_page_id=None,
    )

    assert pages == []


@pytest.mark.asyncio
async def test_explicit_wiki_page_must_be_readable_and_match_knowledge_filter() -> None:
    user_id = uuid4()
    course_id = uuid4()
    knowledge_id = uuid4()
    page_id = uuid4()
    page = SimpleNamespace(
        id=page_id, course_id=course_id, owner_id=user_id, status="active",
        knowledge_id=knowledge_id, title="递归调用栈", summary=None,
        content="递归调用会保存现场。",
    )
    service = EvidenceRetrievalService(db=None)  # type: ignore[arg-type]
    service.courses = MagicMock()
    service.courses.get_by_id = AsyncMock(return_value=None)
    service.wiki = MagicMock()
    service.wiki.get_by_id_simple = AsyncMock(return_value=page)

    readable = await service._load_wiki_pages(
        course_id=course_id, user_id=user_id, question="完全不同的问题",
        knowledge_id=knowledge_id, wiki_page_id=page_id,
    )
    mismatched = await service._load_wiki_pages(
        course_id=course_id, user_id=user_id, question="递归调用栈",
        knowledge_id=uuid4(), wiki_page_id=page_id,
    )

    assert readable == [page]
    assert mismatched == []
