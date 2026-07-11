from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import DocumentChunk
from app.models.knowledge import KnowledgePoint
from app.models.wiki import WikiPage
from app.rag.graph_expansion import GraphExpansionContext
from app.rag.hybrid_retriever import HybridRetriever, RetrievalCandidate
from app.repositories.knowledge_relation_repository import KnowledgeRelationRepository
from app.repositories.knowledge_repository import KnowledgeRepository


class GraphRetriever:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.hybrid = HybridRetriever(db)
        self.relations = KnowledgeRelationRepository(db)
        self.knowledge = KnowledgeRepository(db)

    async def search(
        self,
        *,
        course_id: UUID,
        query: str,
        user_id: UUID | None,
        top_k: int = 8,
        expand_hops: int = 1,
        knowledge_id: UUID | None = None,
    ) -> dict[str, Any]:
        seeds = await self.hybrid.search(
            course_id=course_id,
            query=query,
            user_id=user_id,
            top_k=max(top_k * 2, 10),
            knowledge_id=knowledge_id,
        )
        seed_kp_ids = await self._map_candidates_to_knowledge_ids(seeds, course_id, user_id)
        graph_ctx = GraphExpansionContext()
        if seed_kp_ids:
            scopes = ["public"]
            if user_id:
                scopes.append("personal")
            edges = await self.relations.expand_neighbors(
                course_id,
                seed_kp_ids,
                hops=expand_hops,
                scopes=scopes,
            )
            kp_ids: set[UUID] = set(seed_kp_ids)
            for edge in edges:
                kp_ids.add(edge.source_knowledge_id)
                kp_ids.add(edge.target_knowledge_id)
                graph_ctx.relation_paths.append(
                    {
                        "from_id": str(edge.source_knowledge_id),
                        "to_id": str(edge.target_knowledge_id),
                        "type": edge.relation_type,
                        "evidence": edge.evidence,
                    }
                )

            kp_rows = await self._load_knowledge_points(list(kp_ids))
            seed_set = set(seed_kp_ids)
            graph_ctx.seed_knowledge_ids = [str(kid) for kid in seed_kp_ids]
            graph_ctx.expanded_knowledge_ids = [
                str(kid) for kid in kp_ids if kid not in seed_set
            ]
            graph_ctx.seed_nodes = [
                kp_rows[kid].name for kid in seed_kp_ids if kid in kp_rows
            ]
            graph_ctx.expanded_nodes = [
                kp_rows[kid].name for kid in kp_ids if kid not in seed_set and kid in kp_rows
            ]

        merged = seeds[:top_k]

        return {
            "items": [self._serialize(item) for item in merged],
            "graph_context": graph_ctx.to_dict(),
        }

    async def _map_candidates_to_knowledge_ids(
        self,
        seeds: list[RetrievalCandidate],
        course_id: UUID,
        user_id: UUID | None,
    ) -> list[UUID]:
        ids: list[UUID] = []
        for item in seeds:
            kid = item.extra_meta.get("knowledge_id")
            if kid:
                try:
                    ids.append(UUID(str(kid)))
                    continue
                except ValueError:
                    pass
            result = await self.db.execute(
                select(DocumentChunk.knowledge_id).where(DocumentChunk.id == item.chunk_id)
            )
            row = result.scalar_one_or_none()
            if row:
                ids.append(row)

        return list(dict.fromkeys(ids))

    async def _load_knowledge_points(self, kp_ids: list[UUID]) -> dict[UUID, KnowledgePoint]:
        if not kp_ids:
            return {}
        result = await self.db.execute(select(KnowledgePoint).where(KnowledgePoint.id.in_(kp_ids)))
        return {row.id: row for row in result.scalars().all()}

    async def _candidates_from_knowledge(
        self,
        rows: dict[UUID, KnowledgePoint],
        seed_ids: list[UUID],
    ) -> list[RetrievalCandidate]:
        return []

    def _serialize(self, item: RetrievalCandidate) -> dict[str, Any]:
        return {
            "chunk_id": str(item.chunk_id),
            "material_id": str(item.material_id),
            "content": item.content,
            "source_title": item.source_title,
            "page_no": item.page_no,
            "score": round(item.score, 6),
            "vector_score": round(item.vector_score, 6),
            "keyword_score": round(item.keyword_score, 6),
            "rerank_score": round(item.rerank_score, 6),
            "retrieval_mode": item.retrieval_mode,
            "extra_meta": item.extra_meta,
        }
