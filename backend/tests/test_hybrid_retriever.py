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


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://embedding.example/v1/embeddings")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(
        f"embedding provider returned {status_code}",
        request=request,
        response=response,
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
        ProgrammingError(
            "CREATE EXTENSION vector",
            {},
            Exception('extension "vector" is not available'),
        ),
        httpx.ConnectError(
            "embedding provider unavailable",
            request=httpx.Request("POST", "https://embedding.example/v1/embeddings"),
        ),
        httpx.ReadTimeout(
            "embedding provider timed out",
            request=httpx.Request("POST", "https://embedding.example/v1/embeddings"),
        ),
        _http_status_error(429),
        _http_status_error(503),
        RuntimeError("vector unavailable"),
    ],
    ids=[
        "pgvector-type-missing",
        "pgvector-extension-missing",
        "embedding-connect-error",
        "embedding-timeout",
        "embedding-http-429",
        "embedding-http-503",
        "vector-runtime-unavailable",
    ],
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
        _http_status_error(400),
        _http_status_error(401),
        _http_status_error(403),
        ProgrammingError(
            "SELECT embedding + 1",
            {},
            Exception("operator does not exist: vector + integer"),
        ),
        ProgrammingError(
            "SELECT embedding <=> :query_vec",
            {},
            Exception("operator does not exist: vector <=> text"),
        ),
    ],
    ids=[
        "attribute-error",
        "unrecognized-runtime-error",
        "embedding-http-400",
        "embedding-http-401",
        "embedding-http-403",
        "non-pgvector-operator-mismatch",
        "wrong-vector-operand-type",
    ],
)
async def test_unknown_vector_error_is_not_hidden_by_keyword_fallback(
    vector_error: Exception,
) -> None:
    retriever = HybridRetriever(db=None)  # type: ignore[arg-type]
    retriever._vector_search = AsyncMock(side_effect=vector_error)
    retriever._keyword_search = AsyncMock(return_value=[_keyword_candidate()])

    with pytest.raises(type(vector_error)) as exc_info:
        await retriever.search(uuid4(), "什么是栈？", uuid4(), top_k=5)

    assert exc_info.value is vector_error
    retriever._keyword_search.assert_not_awaited()


def test_query_terms_adds_unique_chinese_windows_and_keeps_domain_terms() -> None:
    terms = _query_terms("递归调用为什么使用栈？再解释复杂度")

    assert "递归" in terms
    assert "调用" in terms
    assert "复杂度" in terms
    assert len(terms) == len(set(terms))
