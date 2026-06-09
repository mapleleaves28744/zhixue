from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_relation import KnowledgeRelation


class KnowledgeRelationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def upsert(
        self,
        *,
        course_id: UUID,
        source_knowledge_id: UUID,
        target_knowledge_id: UUID,
        relation_type: str,
        scope: str,
        evidence: str | None = None,
        confidence: float = 1.0,
        created_by: str = "ai",
        extra_meta: dict | None = None,
    ) -> tuple[KnowledgeRelation, bool]:
        result = await self.db.execute(
            select(KnowledgeRelation).where(
                KnowledgeRelation.course_id == course_id,
                KnowledgeRelation.source_knowledge_id == source_knowledge_id,
                KnowledgeRelation.target_knowledge_id == target_knowledge_id,
                KnowledgeRelation.relation_type == relation_type,
                KnowledgeRelation.scope == scope,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            if evidence and not existing.evidence:
                existing.evidence = evidence
            if confidence > existing.confidence:
                existing.confidence = confidence
            await self.db.flush()
            return existing, False

        relation = KnowledgeRelation(
            course_id=course_id,
            source_knowledge_id=source_knowledge_id,
            target_knowledge_id=target_knowledge_id,
            relation_type=relation_type,
            scope=scope,
            evidence=evidence,
            confidence=confidence,
            created_by=created_by,
            extra_meta=extra_meta or {},
        )
        self.db.add(relation)
        await self.db.flush()
        await self.db.refresh(relation)
        return relation, True

    async def list_by_course(
        self,
        course_id: UUID,
        *,
        scopes: list[str] | None = None,
        source_ids: list[UUID] | None = None,
    ) -> list[KnowledgeRelation]:
        stmt = select(KnowledgeRelation).where(KnowledgeRelation.course_id == course_id)
        if scopes:
            stmt = stmt.where(KnowledgeRelation.scope.in_(scopes))
        if source_ids:
            stmt = stmt.where(KnowledgeRelation.source_knowledge_id.in_(source_ids))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def expand_neighbors(
        self,
        course_id: UUID,
        seed_ids: list[UUID],
        *,
        hops: int = 1,
        scopes: list[str] | None = None,
    ) -> list[KnowledgeRelation]:
        if not seed_ids or hops < 1:
            return []
        collected: list[KnowledgeRelation] = []
        frontier = set(seed_ids)
        visited = set(seed_ids)
        for _ in range(hops):
            if not frontier:
                break
            edges = await self.list_by_course(
                course_id,
                scopes=scopes,
            )
            next_frontier: set[UUID] = set()
            for edge in edges:
                if edge.source_knowledge_id in frontier or edge.target_knowledge_id in frontier:
                    collected.append(edge)
                    for node_id in (edge.source_knowledge_id, edge.target_knowledge_id):
                        if node_id not in visited:
                            visited.add(node_id)
                            next_frontier.add(node_id)
            frontier = next_frontier
        return collected
