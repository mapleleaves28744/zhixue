import logging
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.exc import ProgrammingError

from app.rag.hybrid_retriever import HybridRetriever, RetrievalCandidate, _query_terms


def _keyword_candidate() -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=uuid4(),
        material_id=uuid4(),
        content="栈是 LIFO 结构",
        source_title="数据结构讲义",
        page_no=3,
        keyword_score=2.0,
        keyword_rank=1,
        retrieval_mode="keyword",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "vector_error",
    [
        ProgrammingError(
            "SELECT embedding <=> :query_vec",
            {},
            Exception('type "vector" does not exist'),
        ),
        httpx.ConnectError(
            "embedding provider unavailable",
            request=httpx.Request("POST", "https://embedding.example/v1/embeddings"),
        ),
        RuntimeError("vector unavailable"),
    ],
    ids=["pgvector-unavailable", "embedding-unavailable", "vector-runtime-unavailable"],
)
async def test_known_vector_unavailability_falls_back_to_keyword_candidates(
    vector_error: Exception,
    caplog: pytest.LogCaptureFixture,
) -> None:
    retriever = HybridRetriever(db=None)  # type: ignore[arg-type]
    keyword = _keyword_candidate()
    retriever._vector_search = AsyncMock(side_effect=vector_error)
    retriever._keyword_search = AsyncMock(return_value=[keyword])
    course_id = uuid4()
    user_id = uuid4()
    knowledge_id = uuid4()

    with caplog.at_level(logging.WARNING, logger="app.rag.hybrid_retriever"):
        result = await retriever.search(
            course_id, "什么是栈？", user_id, top_k=5, knowledge_id=knowledge_id
        )

    assert [item.chunk_id for item in result] == [keyword.chunk_id]
    assert "vector retrieval unavailable" in caplog.text.lower()
    retriever._keyword_search.assert_awaited_once_with(
        course_id=course_id,
        query="什么是栈？",
        user_id=user_id,
        top_k=40,
        knowledge_id=knowledge_id,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "vector_error",
    [
        AttributeError("programming bug"),
        RuntimeError("Embedding dimension mismatch: expected 1024, got 768"),
    ],
    ids=["attribute-error", "unrecognized-runtime-error"],
)
async def test_unknown_vector_error_is_not_hidden_by_keyword_fallback(
    vector_error: Exception,
) -> None:
    retriever = HybridRetriever(db=None)  # type: ignore[arg-type]
    retriever._vector_search = AsyncMock(side_effect=vector_error)
    retriever._keyword_search = AsyncMock(return_value=[_keyword_candidate()])

    with pytest.raises(type(vector_error), match=str(vector_error)):
        await retriever.search(uuid4(), "什么是栈？", uuid4(), top_k=5)

    retriever._keyword_search.assert_not_awaited()


def test_query_terms_adds_unique_chinese_windows_and_keeps_domain_terms() -> None:
    terms = _query_terms("递归调用为什么使用栈？再解释复杂度")

    assert "递归" in terms
    assert "调用" in terms
    assert "复杂度" in terms
    assert len(terms) == len(set(terms))
