from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import DocumentChunk
from app.models.knowledge import KnowledgePoint
from app.models.wiki import WikiPage
from app.rag.graph_expansion import GraphExpansionContext
from app.rag.hybrid_retriever import HybridRetriever, RetrievalCandidate, fuse_and_rerank_results
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
    ) -> dict[str, Any]:
        seeds = await self.hybrid.search(
            course_id=course_id,
            query=query,
            user_id=user_id,
            top_k=top_k,
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
            graph_ctx.seed_nodes = [
                kp_rows[kid].name for kid in seed_kp_ids if kid in kp_rows
            ]
            graph_ctx.expanded_nodes = [
                kp_rows[kid].name for kid in kp_ids if kid not in set(seed_kp_ids) and kid in kp_rows
            ]

            expanded_candidates = await self._candidates_from_knowledge(kp_rows, seed_kp_ids)
            merged = fuse_and_rerank_results(query, seeds + expanded_candidates, top_k=top_k)
        else:
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

        if not ids and user_id:
            kps = await self.knowledge.list_visible_by_course(
                course_id=course_id,
                current_user_id=user_id,
                public_owner_id=None,
            )
            for kp in kps[:3]:
                ids.append(kp.id)
        return list(dict.fromkeys(ids))

    async def _load_knowledge_points(self, kp_ids: list[UUID]) -> dict[UUID, KnowledgePoint]:
        if not kp_ids:
            return {}
        result = await self.db.execute(select(KnowledgePoint).where(KnowledgePoint.id.in_(kp_ids)))
        return {row.id: row for row in result.scalars().all()}

    async def _candidates_from_knowledge(
        self,
        kp_map: dict[UUID, KnowledgePoint],
        seed_ids: list[UUID],
    ) -> list[RetrievalCandidate]:
        from uuid import uuid4

        candidates: list[RetrievalCandidate] = []
        seed_set = set(seed_ids)
        for kp_id, kp in kp_map.items():
            if kp_id in seed_set:
                continue
            text = f"{kp.name}：{kp.description or ''}"
            candidates.append(
                RetrievalCandidate(
                    chunk_id=uuid4(),
                    material_id=uuid4(),
                    content=text,
                    source_title=f"知识图谱扩展 · {kp.name}",
                    page_no=None,
                    keyword_score=0.35,
                    extra_meta={"knowledge_id": str(kp_id), "graph_expanded": True},
                    retrieval_mode="graph",
                )
            )
        return candidates

    def _serialize(self, item: RetrievalCandidate) -> dict[str, Any]:
        return {
            "chunk_id": str(item.chunk_id),
            "material_id": str(item.material_id),
            "content": item.content,
            "source_title": item.source_title,
            "page_no": item.page_no,
            "score": round(item.score, 6),
            "retrieval_mode": item.retrieval_mode,
            "extra_meta": item.extra_meta,
        }
