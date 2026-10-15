from __future__ import annotations

from uuid import UUID
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.memory import StudentMemory, StudentMemoryEvidence
from app.models.learning_record import LearningRecord


class MemoryRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def reconciliation_candidates(self, user_id: UUID, course_id: UUID | None) -> list[StudentMemory]:
        scope = StudentMemory.course_id == course_id if course_id else StudentMemory.course_id.is_(None)
        if course_id:
            scope = or_(scope, StudentMemory.course_id.is_(None) &
                        (StudentMemory.lifecycle_meta["scope"].astext == "global") &
                        (StudentMemory.status == "forgotten"))
        return list((await self.db.execute(select(StudentMemory).where(
            StudentMemory.user_id == user_id, scope,
        ).execution_options(populate_existing=True))).scalars().all())

    async def evidence_records(self, memory: StudentMemory) -> list[LearningRecord]:
        linked = select(StudentMemoryEvidence.source_id).where(
            StudentMemoryEvidence.memory_id == memory.id,
            StudentMemoryEvidence.source_type == "learning_record",
        )
        legacy = []
        for value in memory.evidence or []:
            try:
                legacy.append(UUID(str(value)))
            except (TypeError, ValueError):
                continue
        return list((await self.db.execute(select(LearningRecord).where(
            LearningRecord.user_id == memory.user_id,
            or_(LearningRecord.id.in_(linked), LearningRecord.id.in_(legacy)),
        ).order_by(LearningRecord.created_at.desc()).limit(20))).scalars().all())
