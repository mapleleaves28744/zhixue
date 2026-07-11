from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.rag.graph_retriever import GraphRetriever


def test_graph_retriever_serialize_shape() -> None:
    retriever = GraphRetriever.__new__(GraphRetriever)
    item = retriever._serialize(
        type(
            "Candidate",
            (),
            {
                "chunk_id": uuid4(),
                "material_id": uuid4(),
                "content": "栈是一种 LIFO 结构",
                "source_title": "数据结构讲义",
                "page_no": 3,
                "score": 0.8123456,
                "vector_score": 0.7123456,
                "keyword_score": 1.2345678,
                "rerank_score": 0.8123456,
                "retrieval_mode": "hybrid",
                "extra_meta": {"knowledge_id": str(uuid4())},
            },
        )()
    )
    assert item["content"].startswith("栈")
    assert item["retrieval_mode"] == "hybrid"
    assert isinstance(item["score"], float)
    assert item["vector_score"] == 0.712346
    assert item["keyword_score"] == 1.234568
    assert item["rerank_score"] == 0.812346


@pytest.mark.asyncio
async def test_graph_expansion_does_not_create_synthetic_document_candidates() -> None:
    retriever = GraphRetriever.__new__(GraphRetriever)
    rows = {uuid4(): MagicMock(name="BFS", description="广度优先搜索")}
    assert await retriever._candidates_from_knowledge(rows, []) == []


@pytest.mark.asyncio
async def test_unmapped_chunks_do_not_fallback_to_arbitrary_knowledge_points() -> None:
    retriever = GraphRetriever.__new__(GraphRetriever)
    retriever.db = MagicMock()
    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = None
    retriever.db.execute = AsyncMock(return_value=db_result)
    retriever.knowledge = MagicMock()
    retriever.knowledge.list_visible_by_course = AsyncMock(
        return_value=[MagicMock(id=uuid4())]
    )
    from app.rag.hybrid_retriever import RetrievalCandidate

    seed = RetrievalCandidate(
        chunk_id=uuid4(), material_id=uuid4(), content="无映射片段",
        source_title="讲义", page_no=None,
    )

    result = await retriever._map_candidates_to_knowledge_ids(
        [seed], uuid4(), uuid4()
    )

    assert result == []
    retriever.knowledge.list_visible_by_course.assert_not_awaited()


def test_wiki_graph_service_exports_get_graph() -> None:
    from app.services.wiki_graph_service import WikiGraphService

    assert hasattr(WikiGraphService, "get_graph")
    assert hasattr(WikiGraphService, "get_subgraph")


def test_graph_retriever_search_returns_graph_context(monkeypatch) -> None:
    import asyncio

    async def _run() -> None:
        kid = uuid4()
        retriever = GraphRetriever.__new__(GraphRetriever)
        retriever.db = MagicMock()
        retriever.hybrid = MagicMock()
        retriever.relations = MagicMock()
        retriever.knowledge = MagicMock()

        from app.rag.hybrid_retriever import RetrievalCandidate

        seed = RetrievalCandidate(
            chunk_id=uuid4(),
            material_id=uuid4(),
            content="栈是后进先出结构",
            source_title="讲义",
            page_no=1,
            keyword_score=0.8,
            extra_meta={"knowledge_id": str(kid)},
            retrieval_mode="hybrid",
        )
        retriever.hybrid.search = AsyncMock(return_value=[seed])
        retriever.relations.expand_neighbors = AsyncMock(return_value=[])
        retriever._map_candidates_to_knowledge_ids = AsyncMock(return_value=[kid])
        retriever._load_knowledge_points = AsyncMock(
            return_value={kid: MagicMock(name="栈", description="LIFO")}
        )
        retriever._candidates_from_knowledge = AsyncMock(return_value=[])

        payload = await retriever.search(
            course_id=uuid4(),
            query="栈",
            user_id=uuid4(),
            top_k=3,
            expand_hops=1,
            knowledge_id=kid,
        )
        assert isinstance(payload["items"], list)
        assert payload["items"]
        assert "seed_nodes" in payload["graph_context"]
        assert payload["graph_context"]["seed_knowledge_ids"] == [str(kid)]
        assert payload["graph_context"]["expanded_knowledge_ids"] == []
        assert retriever.hybrid.search.await_args.kwargs["knowledge_id"] == kid
        assert retriever.hybrid.search.await_args.kwargs["top_k"] == 10

    asyncio.run(_run())
