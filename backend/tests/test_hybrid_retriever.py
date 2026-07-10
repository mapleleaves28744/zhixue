from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.rag.hybrid_retriever import HybridRetriever, RetrievalCandidate, _query_terms


@pytest.mark.asyncio
async def test_vector_failure_falls_back_to_keyword_candidates() -> None:
    retriever = HybridRetriever(db=None)  # type: ignore[arg-type]
    keyword = RetrievalCandidate(
        chunk_id=uuid4(),
        material_id=uuid4(),
        content="栈是 LIFO 结构",
        source_title="数据结构讲义",
        page_no=3,
        keyword_score=2.0,
        keyword_rank=1,
        retrieval_mode="keyword",
    )
    retriever._vector_search = AsyncMock(side_effect=RuntimeError("vector unavailable"))
    retriever._keyword_search = AsyncMock(return_value=[keyword])
    course_id = uuid4()
    user_id = uuid4()
    knowledge_id = uuid4()

    result = await retriever.search(
        course_id, "什么是栈？", user_id, top_k=5, knowledge_id=knowledge_id
    )

    assert [item.chunk_id for item in result] == [keyword.chunk_id]
    retriever._keyword_search.assert_awaited_once_with(
        course_id=course_id,
        query="什么是栈？",
        user_id=user_id,
        top_k=40,
        knowledge_id=knowledge_id,
    )


def test_query_terms_adds_unique_chinese_windows_and_keeps_domain_terms() -> None:
    terms = _query_terms("递归调用为什么使用栈？再解释复杂度")

    assert "递归" in terms
    assert "调用" in terms
    assert "复杂度" in terms
    assert len(terms) == len(set(terms))
