from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgePoint
from app.models.user import User
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.mastery_repository import MasteryRepository


class MasteryService:
    """BKT 简化版 + 艾宾浩斯遗忘曲线，掌握度单一事实源。"""

    LEARN_RATE = 0.25
    FORGET_BASE = 0.04
    ASK_WEAK_PENALTY = 0.03
    ASK_REVIEW_BONUS = 0.02

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = MasteryRepository(db)
        self.knowledge = KnowledgeRepository(db)

    async def get_mastery_map(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        apply_decay: bool = False,
    ) -> dict[str, float]:
        rows = await self.repo.list_for_course(user_id=user_id, course_id=course_id)
        if apply_decay:
            now = datetime.now(UTC)
            for row in rows:
                before = float(row.mastery_score)
                self._apply_decay(row, now)
                if float(row.mastery_score) != before:
                    await self.repo.save(row)
            await self.db.flush()
        return {str(row.knowledge_id): float(row.mastery_score) for row in rows}

    async def list_mastery_items(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
    ) -> list[dict[str, Any]]:
        rows = await self.repo.list_for_course(user_id=user_id, course_id=course_id)
        kp_ids = [row.knowledge_id for row in rows]
        kp_map: dict[UUID, KnowledgePoint] = {}
        if kp_ids:
            for kp in await self.knowledge.list_visible_by_course(
                course_id=course_id,
                current_user_id=user_id,
                public_owner_id=None,
                include_all=True,
            ):
                if kp.id in kp_ids:
                    kp_map[kp.id] = kp

        items: list[dict[str, Any]] = []
        for row in rows:
            kp = kp_map.get(row.knowledge_id)
            items.append(
                {
                    "knowledge_id": str(row.knowledge_id),
                    "knowledge_name": kp.name if kp else "知识点",
                    "mastery_score": round(float(row.mastery_score), 3),
                    "attempt_count": row.attempt_count,
                    "correct_count": row.correct_count,
                    "ask_count": row.ask_count,
                    "stability": round(float(row.stability), 2),
                    "evidence": row.evidence_json,
                }
            )
        return sorted(items, key=lambda x: x["mastery_score"])

    async def apply_practice_update(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        knowledge_id: UUID,
        is_correct: bool,
    ) -> dict[str, Any]:
        row = await self.repo.get_or_create(
            user_id=user_id,
            course_id=course_id,
            knowledge_id=knowledge_id,
        )
        now = datetime.now(UTC)
        row = self._apply_decay(row, now)

        if is_correct:
            row.mastery_score = min(
                1.0,
                float(row.mastery_score) + self.LEARN_RATE * max(0.15, 1.0 - float(row.mastery_score)),
            )
            row.stability = min(30.0, float(row.stability) + 0.8)
            row.correct_count += 1
        else:
            row.mastery_score = max(0.0, float(row.mastery_score) - self.LEARN_RATE * 0.75)
            row.stability = max(0.5, float(row.stability) * 0.85)

        row.attempt_count += 1
        row.last_practiced_at = now
        row.evidence_json = {
            "source": "practice",
            "summary": (
                f"练习 {row.attempt_count} 次，正确率 "
                f"{row.correct_count / row.attempt_count:.0%}，掌握度 {row.mastery_score:.0%}"
            ),
            "attempt_count": row.attempt_count,
            "correct_count": row.correct_count,
        }
        await self.repo.save(row)
        return {"knowledge_id": str(knowledge_id), "mastery_score": float(row.mastery_score)}

    async def apply_ask_update(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        knowledge_id: UUID,
        understood: bool = False,
    ) -> dict[str, Any]:
        row = await self.repo.get_or_create(
            user_id=user_id,
            course_id=course_id,
            knowledge_id=knowledge_id,
        )
        now = datetime.now(UTC)
        row = self._apply_decay(row, now)
        row.ask_count += 1
        row.last_asked_at = now

        if understood:
            row.mastery_score = min(1.0, float(row.mastery_score) + self.ASK_REVIEW_BONUS)
        elif row.ask_count >= 2:
            row.mastery_score = max(0.0, float(row.mastery_score) - self.ASK_WEAK_PENALTY)

        row.evidence_json = {
            "source": "dialogue",
            "summary": f"对话提及 {row.ask_count} 次，掌握度 {row.mastery_score:.0%}",
            "ask_count": row.ask_count,
        }
        await self.repo.save(row)
        return {"knowledge_id": str(knowledge_id), "mastery_score": float(row.mastery_score)}

    async def sync_profile_snapshot(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
    ) -> dict[str, Any]:
        from sqlalchemy import select

        from app.models.profile import StudentCourseProfile

        items = await self.list_mastery_items(user_id=user_id, course_id=course_id)
        flat: dict[str, Any] = {}
        for item in items:
            flat[item["knowledge_id"]] = item["mastery_score"]
            flat[item["knowledge_name"]] = item["mastery_score"]
        flat["_course_id"] = str(course_id)
        flat["_overall"] = (
            round(sum(item["mastery_score"] for item in items) / len(items), 2) if items else 0.0
        )
        flat["_items"] = items

        result = await self.db.execute(select(StudentCourseProfile).where(
            StudentCourseProfile.user_id == user_id, StudentCourseProfile.course_id == course_id
        ))
        profile = result.scalar_one_or_none()
        if profile is None:
            profile = StudentCourseProfile(user_id=user_id, course_id=course_id)
            self.db.add(profile)
        profile.mastery_snapshot = flat
        profile.version_no += 1
        await self.db.flush()
        return flat

    def _apply_decay(self, row: Any, now: datetime) -> Any:
        ref = row.last_practiced_at or row.last_asked_at
        if ref is None:
            return row
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=UTC)
        days = max(0.0, (now - ref).total_seconds() / 86400.0)
        if days <= 0:
            return row
        stability = max(0.5, float(row.stability))
        retention = math.exp(-days / stability)
        decayed = float(row.mastery_score) * retention
        row.mastery_score = max(0.05, decayed - self.FORGET_BASE * days)
        row.evidence_json = {
            **(row.evidence_json or {}),
            "decay_days": round(days, 1),
            "retention": round(retention, 3),
        }
        return row
