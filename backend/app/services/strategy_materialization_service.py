from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evolution import EvolutionStrategy
from app.models.profile import LearningPreference, StudentCourseProfile


class StrategyMaterializationService:
    EXECUTABLE_TYPES = {"qa_style", "resource_strategy", "difficulty", "recommendation", "learning_path"}

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @classmethod
    def normalize_strategy_type(cls, value: str) -> str:
        return value if value in cls.EXECUTABLE_TYPES else "recommendation"

    async def materialize(self, strategy: EvolutionStrategy, *, rollback: bool = False) -> dict[str, Any]:
        values = dict(strategy.before_value if rollback else strategy.after_value)
        strategy_type = self.normalize_strategy_type(strategy.strategy_type)
        changes: dict[str, Any] = {"strategy_type": strategy_type, "values": values, "rollback": rollback}

        if strategy_type in {"qa_style", "resource_strategy"}:
            preference = await self._preference(strategy)
            if strategy_type == "qa_style":
                if values.get("answer_length"):
                    preference.answer_length = str(values["answer_length"])
                if values.get("explanation_style"):
                    preference.explanation_style = str(values["explanation_style"])
                preference.prompt_params = {**(preference.prompt_params or {}), **values}
            else:
                preference.resource_preferences = list(values.get("resource_preferences") or values.get("types") or [])
                preference.prompt_params = {**(preference.prompt_params or {}), "resource_strategy": values}
            preference.version_no += 1
        else:
            profile = await self._course_profile(strategy)
            profile.strategy_summary = {**(profile.strategy_summary or {}), strategy_type: values}
            profile.version_no += 1

        strategy.materialized_changes = changes
        strategy.applied_at = datetime.now(UTC) if not rollback else strategy.applied_at
        strategy.evaluation_status = "collecting" if not rollback else "rolled_back"
        return changes

    async def _preference(self, strategy: EvolutionStrategy) -> LearningPreference:
        result = await self.db.execute(select(LearningPreference).where(
            LearningPreference.user_id == strategy.user_id,
            LearningPreference.course_id == strategy.course_id,
        ))
        item = result.scalar_one_or_none()
        if item is None:
            item = LearningPreference(user_id=strategy.user_id, course_id=strategy.course_id)
            self.db.add(item)
            await self.db.flush()
        return item

    async def _course_profile(self, strategy: EvolutionStrategy) -> StudentCourseProfile:
        result = await self.db.execute(select(StudentCourseProfile).where(
            StudentCourseProfile.user_id == strategy.user_id,
            StudentCourseProfile.course_id == strategy.course_id,
        ))
        item = result.scalar_one_or_none()
        if item is None:
            item = StudentCourseProfile(user_id=strategy.user_id, course_id=strategy.course_id)
            self.db.add(item)
            await self.db.flush()
        return item
