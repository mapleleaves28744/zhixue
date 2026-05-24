from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.profile import LearningPreference, StudentProfile
from app.schemas.profile import (
    LearningPreferenceRead,
    ProfileRead,
    ProfileSummary,
    ProfileUpdate,
)


class ProfileService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_profile(self, user_id: UUID) -> ProfileRead:
        profile = await self._get_or_create(user_id)
        return ProfileRead.model_validate(profile)

    async def update_profile(
        self, user_id: UUID, payload: ProfileUpdate
    ) -> ProfileRead:
        profile = await self._get_or_create(user_id)
        values = payload.model_dump(exclude_unset=True)
        for key, value in values.items():
            setattr(profile, key, value)
        profile.version_no += 1
        await self.db.commit()
        await self.db.refresh(profile)
        return ProfileRead.model_validate(profile)

    async def get_summary(self, user_id: UUID) -> ProfileSummary:
        profile = await self._get_or_create(user_id)
        return ProfileSummary.model_validate(profile)

    async def rebuild(self, user_id: UUID) -> ProfileRead:
        from app.agents.context import AgentContext
        from app.agents.profile_agent import ProfileAgent

        agent = ProfileAgent(self.db)
        context = AgentContext(
            user_id=user_id,
            course_id=user_id,
            task_type="profile_rebuild",
            params={"action": "rebuild"},
        )
        result = await agent.run(context)
        if not result.success:
            raise BusinessException(
                code=ErrorCode.LLM_CALL_FAILED,
                detail=result.message,
                status_code=500,
            )
        profile = await self._get_or_create(user_id)
        return ProfileRead.model_validate(profile)

    async def get_preferences(
        self, user_id: UUID, course_id: UUID | None = None
    ) -> list[LearningPreferenceRead]:
        stmt = select(LearningPreference).where(
            LearningPreference.user_id == user_id
        )
        if course_id is not None:
            stmt = stmt.where(LearningPreference.course_id == course_id)
        result = await self.db.execute(stmt)
        prefs = result.scalars().all()
        return [LearningPreferenceRead.model_validate(p) for p in prefs]

    async def _get_or_create(self, user_id: UUID) -> StudentProfile:
        stmt = select(StudentProfile).where(StudentProfile.user_id == user_id)
        result = await self.db.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile is None:
            profile = StudentProfile(user_id=user_id)
            self.db.add(profile)
            await self.db.commit()
            await self.db.refresh(profile)
        return profile
