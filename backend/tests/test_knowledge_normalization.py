from __future__ import annotations

from uuid import uuid4

import pytest

from app.services.knowledge_service import KnowledgeService
from app.services.knowledge_normalization_service import (
    KnowledgeCandidate,
    KnowledgeNormalizationService,
)


def candidate(name: str, order: int = 0) -> KnowledgeCandidate:
    return KnowledgeCandidate(
        raw_name=name,
        description=f"{name}的资料定义",
        chapter="栈与队列",
        source_chunk_ids=[uuid4()],
        source_order=order,
    )


def test_clean_candidate_name_and_reject_sentence_noise() -> None:
    service = KnowledgeNormalizationService(db=None)

    assert service.clean_candidate_name("** 1. 链式栈 **") == "链式栈"
    assert service.is_valid_name("链式栈")
    assert not service.is_valid_name("按位访问 O(n)，插入删除后继 O(1)")
    assert not service.is_valid_name("**")
    assert not service.is_valid_name("1")


@pytest.mark.asyncio
async def test_rule_fallback_deduplicates_rejects_noise_and_caps_at_30() -> None:
    service = KnowledgeNormalizationService(db=None)
    candidates = [candidate("链式栈", 0), candidate("**链式栈**", 1), candidate("与场景**", 2)]
    candidates.extend(candidate(f"有效知识点{i}", i + 3) for i in range(35))

    result = await service.normalize(
        candidates=candidates,
        course_id=uuid4(),
        owner_id=uuid4(),
    )

    assert result.used_llm is False
    assert result.fallback_reason
    assert result.candidate_count == len(candidates)
    assert result.kept_count == 30
    assert result.merged_count >= 1
    assert result.rejected_count >= 1
    assert len({item.canonical_name for item in result.items}) == result.kept_count
    assert all(item.source_chunk_ids for item in result.items)


@pytest.mark.asyncio
async def test_rule_fallback_merges_common_data_structure_aliases() -> None:
    service = KnowledgeNormalizationService(db=None)

    result = await service.normalize(
        candidates=[
            candidate("链栈", 0),
            candidate("链式栈", 1),
            candidate("栈的链式存储", 2),
        ],
        course_id=uuid4(),
        owner_id=uuid4(),
    )

    assert result.kept_count == 1
    assert result.items[0].canonical_name == "链式栈"
    assert set(result.items[0].aliases) == {"链栈", "栈的链式存储"}


def test_rule_candidates_keep_source_chunk_ids_and_order() -> None:
    service = KnowledgeService.__new__(KnowledgeService)
    first_id = uuid4()
    second_id = uuid4()
    chunks = [
        type("Chunk", (), {"id": first_id, "content": "## 栈\n栈是后进先出的线性表。"})(),
        type("Chunk", (), {"id": second_id, "content": "1. 链式栈\n链式栈指使用链表实现的栈。"})(),
    ]

    candidates = service._extract_candidates_from_chunks(chunks)

    assert candidates
    assert candidates[0].source_order == 0
    assert all(item.source_chunk_ids for item in candidates)
    assert {chunk_id for item in candidates for chunk_id in item.source_chunk_ids} == {
        first_id,
        second_id,
    }
