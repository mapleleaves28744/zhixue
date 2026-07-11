from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evolution import EvolutionStrategy
from app.models.profile import LearningPreference, StudentCourseProfile, StudentProfile
from app.services.memory_service import MemoryService


class PersonalizationContextService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_context(self, user_id: UUID, course_id: UUID) -> dict[str, Any]:
        global_profile = (await self.db.execute(select(StudentProfile).where(StudentProfile.user_id == user_id))).scalar_one_or_none()
        course_profile = (await self.db.execute(select(StudentCourseProfile).where(
            StudentCourseProfile.user_id == user_id, StudentCourseProfile.course_id == course_id
        ))).scalar_one_or_none()
        preference = (await self.db.execute(select(LearningPreference).where(
            LearningPreference.user_id == user_id, LearningPreference.course_id == course_id
        ).order_by(LearningPreference.version_no.desc()).limit(1))).scalar_one_or_none()
        strategies = list((await self.db.execute(select(EvolutionStrategy).where(
            EvolutionStrategy.user_id == user_id,
            EvolutionStrategy.course_id == course_id,
            EvolutionStrategy.status == "active",
        ))).scalars().all())
        memories = await MemoryService(self.db).list_memories(user_id, course_id, status="active", limit=5)
        return {
            "global_profile": global_profile,
            "course_profile": course_profile,
            "preference": preference,
            "strategies": {item.strategy_type: item for item in strategies},
            "memories": memories,
        }

    @staticmethod
    def format_for_prompt(context: dict[str, Any]) -> str:
        parts: list[str] = []
        global_profile = context.get("global_profile")
        course_profile = context.get("course_profile")
        preference = context.get("preference")
        if global_profile and global_profile.profile_summary:
            parts.append(f"全局画像：{global_profile.profile_summary}")
        if course_profile:
            parts.append(f"课程画像：{course_profile.profile_summary or '正在积累'}")
            if course_profile.weak_points:
                parts.append(f"课程薄弱点：{course_profile.weak_points}")
        if preference:
            parts.append(f"回答偏好：长度={preference.answer_length or '默认'}，风格={preference.explanation_style or '默认'}，参数={preference.prompt_params}")
        if context.get("memories"):
            parts.append("相关活跃记忆：" + "；".join(item.content for item in context["memories"]))
        if context.get("strategies"):
            parts.append("当前生效策略：" + "；".join(f"{key}={item.after_value}" for key, item in context["strategies"].items()))
        return "\n".join(parts) or "暂无个性化证据，使用通用教学策略。"

    @staticmethod
    def format_profile_for_prompt(context: dict[str, Any]) -> str:
        profile_only = {**context, "memories": []}
        return PersonalizationContextService.format_for_prompt(profile_only)

    @staticmethod
    def format_memories_for_prompt(context: dict[str, Any]) -> str:
        memories = context.get("memories") or []
        return "；".join(item.content for item in memories) or "暂无可用长期学习记忆。"
