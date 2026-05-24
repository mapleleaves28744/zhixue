from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learning_record import LearningRecord


class LearningRecordService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record_event(
        self,
        *,
        user_id: UUID,
        course_id: UUID | None = None,
        knowledge_id: UUID | None = None,
        event_type: str,
        event_source: str | None = None,
        event_payload: dict[str, Any] | None = None,
    ) -> LearningRecord:
        record = LearningRecord(
            user_id=user_id,
            course_id=course_id,
            knowledge_id=knowledge_id,
            event_type=event_type,
            event_source=event_source,
            event_payload=event_payload or {},
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def list_records(
        self,
        user_id: UUID,
        course_id: UUID | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[LearningRecord]:
        stmt = select(LearningRecord).where(LearningRecord.user_id == user_id)
        if course_id is not None:
            stmt = stmt.where(LearningRecord.course_id == course_id)
        if event_type is not None:
            stmt = stmt.where(LearningRecord.event_type == event_type)
        stmt = stmt.order_by(LearningRecord.created_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
