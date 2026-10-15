from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import StudentMemory, StudentMemoryEvidence


class MemorySuppressionService:
    """Find learning records whose derived memory was explicitly forgotten."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def source_record_ids(self, *, user_id: UUID, course_id: UUID | None) -> set[str]:
        global_scope = (
            StudentMemory.course_id.is_(None)
            & (StudentMemory.lifecycle_meta["scope"].astext == "global")
        )
        scope = or_(StudentMemory.course_id == course_id, global_scope) if course_id else global_scope
        memories = list((await self.db.execute(select(StudentMemory).where(
            StudentMemory.user_id == user_id,
            StudentMemory.status == "forgotten",
            scope,
        ))).scalars().all())
        if not memories:
            return set()
        memory_ids = [item.id for item in memories]
        linked = (await self.db.execute(select(StudentMemoryEvidence.source_id).where(
            StudentMemoryEvidence.memory_id.in_(memory_ids),
            StudentMemoryEvidence.source_type == "learning_record",
        ))).scalars().all()
        source_ids = {str(item) for item in linked}
        for memory in memories:
            for item in memory.evidence or []:
                try:
                    source_ids.add(str(UUID(str(item))))
                except (TypeError, ValueError):
                    continue
        return source_ids
