from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

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
                "retrieval_mode": "hybrid",
                "extra_meta": {"knowledge_id": str(uuid4())},
            },
        )()
    )
    assert item["content"].startswith("栈")
    assert item["retrieval_mode"] == "hybrid"
    assert isinstance(item["score"], float)


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
        )
        assert isinstance(payload["items"], list)
        assert payload["items"]
        assert "seed_nodes" in payload["graph_context"]

    asyncio.run(_run())
