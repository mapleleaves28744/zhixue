from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.student_knowledge_mastery import StudentKnowledgeMastery


class MasteryRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        knowledge_id: UUID,
    ) -> StudentKnowledgeMastery | None:
        result = await self.db.execute(
            select(StudentKnowledgeMastery).where(
                StudentKnowledgeMastery.user_id == user_id,
                StudentKnowledgeMastery.course_id == course_id,
                StudentKnowledgeMastery.knowledge_id == knowledge_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_course(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
    ) -> list[StudentKnowledgeMastery]:
        result = await self.db.execute(
            select(StudentKnowledgeMastery).where(
                StudentKnowledgeMastery.user_id == user_id,
                StudentKnowledgeMastery.course_id == course_id,
            )
        )
        return list(result.scalars().all())

    async def get_or_create(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        knowledge_id: UUID,
    ) -> StudentKnowledgeMastery:
        row = await self.get(user_id=user_id, course_id=course_id, knowledge_id=knowledge_id)
        if row:
            return row
        row = StudentKnowledgeMastery(
            user_id=user_id,
            course_id=course_id,
            knowledge_id=knowledge_id,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def save(self, row: StudentKnowledgeMastery) -> StudentKnowledgeMastery:
        row.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(row)
        return row
