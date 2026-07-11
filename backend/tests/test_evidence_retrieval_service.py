from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import BusinessException
from app.services.evidence_retrieval_service import EvidenceRetrievalService


def _document_item(material_id: object, *, index: int) -> dict[str, object]:
    return {
        "chunk_id": str(uuid4()),
        "material_id": str(material_id),
        "content": f"栈相关文档片段 {index}",
        "source_title": "数据结构讲义",
        "vector_score": 0.8,
        "keyword_score": 0.0,
        "score": 0.8,
        "retrieval_mode": "vector",
        "extra_meta": {},
    }


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


@pytest.mark.asyncio
async def test_explicit_wiki_precedes_documents_and_deduplicated_auto_wiki() -> None:
    user_id = uuid4()
    course_id = uuid4()
    knowledge_id = uuid4()
    material_id = uuid4()
    second_material_id = uuid4()
    explicit = SimpleNamespace(
        id=uuid4(), course_id=course_id, owner_id=user_id, status="active",
        knowledge_id=knowledge_id, title="栈的显式页面", summary="显式选择",
        content="栈是后进先出结构。",
    )
    automatic = SimpleNamespace(
        id=uuid4(), course_id=course_id, owner_id=user_id, status="active",
        knowledge_id=knowledge_id, title="栈如何工作", summary="自动匹配",
        content="栈支持入栈和出栈。",
    )
    service = EvidenceRetrievalService(db=None)  # type: ignore[arg-type]
    service.graph.search = AsyncMock(
        return_value={
            "items": [
                *[_document_item(material_id, index=index) for index in range(5)],
                _document_item(second_material_id, index=5),
            ],
            "graph_context": {},
        }
    )
    service.courses = MagicMock()
    service.courses.get_by_id = AsyncMock(
        return_value=SimpleNamespace(
            owner_id=user_id, visibility="private", status="active"
        )
    )
    service.wiki = MagicMock()
    service.wiki.get_by_id_simple = AsyncMock(return_value=explicit)
    service.wiki.list_by_owners = AsyncMock(
        return_value=([explicit, automatic, explicit], 3)
    )

    bundle = await service.retrieve(
        course_id=course_id, user_id=user_id, question="栈如何工作？", top_k=5,
        knowledge_id=knowledge_id, wiki_page_id=explicit.id,
        use_rag=True, use_wiki=True,
    )

    assert [item.retrieval_mode for item in bundle.evidence] == [
        "wiki_explicit", "vector", "vector", "vector", "wiki_match"
    ]
    assert [item.source_id for item in bundle.evidence].count(explicit.id) == 1
    assert [item.source_id for item in bundle.evidence].count(material_id) == 2
    assert bundle.evidence[-1].source_id == automatic.id
    assert [item.citation_key for item in bundle.evidence] == [
        "S1", "S2", "S3", "S4", "S5"
    ]


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
async def test_auto_wiki_matching_rechecks_course_status_and_allowed_owner() -> None:
    user_id = uuid4()
    course_id = uuid4()
    public_owner_id = uuid4()
    common = {
        "knowledge_id": None,
        "title": "栈结构",
        "summary": "后进先出",
        "content": "栈支持入栈和出栈。",
    }
    user_page = SimpleNamespace(
        id=uuid4(), course_id=course_id, owner_id=user_id, status="active", **common
    )
    public_page = SimpleNamespace(
        id=uuid4(), course_id=course_id, owner_id=public_owner_id, status="active", **common
    )
    wrong_course = SimpleNamespace(
        id=uuid4(), course_id=uuid4(), owner_id=user_id, status="active", **common
    )
    wrong_owner = SimpleNamespace(
        id=uuid4(), course_id=course_id, owner_id=uuid4(), status="active", **common
    )
    inactive = SimpleNamespace(
        id=uuid4(), course_id=course_id, owner_id=user_id, status="archived", **common
    )
    service = EvidenceRetrievalService(db=None)  # type: ignore[arg-type]
    service.courses = MagicMock()
    service.courses.get_by_id = AsyncMock(
        return_value=SimpleNamespace(
            owner_id=public_owner_id, visibility="public_template", status="active"
        )
    )
    service.wiki = MagicMock()
    service.wiki.list_by_owners = AsyncMock(
        return_value=([wrong_course, wrong_owner, inactive, user_page, public_page], 5)
    )

    pages = await service._load_wiki_pages(
        course_id=course_id, user_id=user_id, question="栈结构是什么？",
        knowledge_id=None, wiki_page_id=None,
    )

    assert pages == [user_page, public_page]


@pytest.mark.parametrize(
    ("item", "terms", "expected_confidence"),
    [
        ({"keyword_score": 1.0, "vector_score": 0.0, "content": "栈遵循后进先出"}, ["栈"], "strong"),
        ({"keyword_score": 0.0, "vector_score": 0.55}, ["栈"], "strong"),
        (
            {
                "keyword_score": 0.0,
                "vector_score": 0.45,
                "source_title": "数据结构：栈",
            },
            ["栈"],
            "acceptable",
        ),
    ],
    ids=["keyword-1.0", "vector-0.55", "title-hit-vector-0.45"],
)
def test_document_acceptance_includes_exact_confidence_boundaries(
    item: dict[str, object],
    terms: list[str],
    expected_confidence: str,
) -> None:
    service = EvidenceRetrievalService(db=None)  # type: ignore[arg-type]

    assert service._accept_document(item, terms) is True
    assert service._confidence(item) == expected_confidence


def test_keyword_evidence_requires_discriminative_question_overlap() -> None:
    service = EvidenceRetrievalService(db=None)  # type: ignore[arg-type]
    item = {
        "keyword_score": 4.5,
        "vector_score": 0.0,
        "source_title": "数据结构讲义",
        "content": "本页用于课程知识库和学生复习资料。",
    }

    assert service._accept_document(
        item,
        ["数据结构", "课程", "资料", "量子", "纠缠", "贝尔", "不等式"],
    ) is False


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
    service.wiki.list_by_owners = AsyncMock(return_value=([], 0))

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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("page_overrides", "expected_status"),
    [
        ({"course_id": uuid4()}, 404),
        ({"owner_id": uuid4()}, 404),
        ({"status": "archived"}, 400),
    ],
    ids=["other-course", "other-owner", "archived"],
)
async def test_explicit_wiki_page_preserves_chat_error_semantics(
    page_overrides: dict[str, object], expected_status: int
) -> None:
    user_id = uuid4()
    course_id = uuid4()
    page = SimpleNamespace(**{
        "id": uuid4(), "course_id": course_id, "owner_id": user_id,
        "status": "active", "knowledge_id": None, "title": "递归调用栈",
        "summary": None, "content": "递归现场。", **page_overrides,
    })
    service = EvidenceRetrievalService(db=None)  # type: ignore[arg-type]
    service.courses = MagicMock()
    service.courses.get_by_id = AsyncMock(return_value=None)
    service.wiki = MagicMock()
    service.wiki.get_by_id_simple = AsyncMock(return_value=page)

    with pytest.raises(BusinessException) as exc_info:
        await service.require_readable_wiki_page(
            course_id=course_id,
            user_id=user_id,
            wiki_page_id=page.id,
            is_admin=False,
        )

    assert exc_info.value.status_code == expected_status
