from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import UserFeedback


class FeedbackRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        user_id: UUID,
        course_id: UUID | None,
        target_type: str,
        target_id: UUID,
        feedback_type: str,
        rating: int | None = None,
        comment: str | None = None,
    ) -> UserFeedback:
        feedback = UserFeedback(
            user_id=user_id,
            course_id=course_id,
            target_type=target_type,
            target_id=target_id,
            feedback_type=feedback_type,
            rating=rating,
            comment=comment,
        )
        self.db.add(feedback)
        await self.db.flush()
        await self.db.refresh(feedback)
        return feedback
