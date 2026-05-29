from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.diagnosis import DiagnosisReport
from app.models.learning_path import LearningPath, LearningPathItem
from app.models.recommendation import Recommendation
from app.models.user import User
from app.services.course_service import CourseService


class RecommendationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_recommendations(
        self,
        *,
        current_user: User,
        course_id: UUID | None = None,
        status: str | None = "pending",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = select(Recommendation).where(Recommendation.user_id == current_user.id)
        if course_id is not None:
            await CourseService(self.db).get_readable_course(course_id, current_user)
            stmt = stmt.where(Recommendation.course_id == course_id)
        if status is not None:
            stmt = stmt.where(Recommendation.status == status)

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(total_stmt)).scalar() or 0
        stmt = (
            stmt.order_by(Recommendation.priority.asc(), Recommendation.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        return [self._serialize(item) for item in result.scalars().all()], total

    async def refresh_recommendations(
        self,
        *,
        current_user: User,
        course_id: UUID,
    ) -> dict[str, Any]:
        await CourseService(self.db).get_readable_course(course_id, current_user)

        existing = await self.db.execute(
            select(Recommendation).where(
                Recommendation.user_id == current_user.id,
                Recommendation.course_id == course_id,
                Recommendation.status == "pending",
            )
        )
        for item in existing.scalars().all():
            item.status = "stale"

        created = 0
        for payload in await self._build_payloads(current_user.id, course_id):
            self.db.add(Recommendation(**payload))
            created += 1

        await self.db.commit()
        return {"refreshed_count": created, "message": "推荐已刷新"}

    async def update_status(
        self,
        *,
        item_id: UUID,
        current_user: User,
        status: str,
    ) -> dict[str, Any]:
        item = await self._get_owned_recommendation(item_id, current_user.id)
        if status not in {"pending", "completed", "ignored", "stale"}:
            raise BusinessException(code=ErrorCode.PARAM_ERROR, detail="推荐状态不合法", status_code=400)

        item.status = status
        item.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(item)
        return self._serialize(item)

    async def submit_feedback(
        self,
        *,
        item_id: UUID,
        current_user: User,
        helpful: bool | None = None,
    ) -> dict[str, Any]:
        item = await self._get_owned_recommendation(item_id, current_user.id)
        if helpful is False and item.status == "pending":
            item.status = "ignored"
            item.updated_at = datetime.now(UTC)
            await self.db.commit()
            await self.db.refresh(item)
        return {"id": str(item.id), "message": "反馈已记录", "status": item.status}

    async def _build_payloads(self, user_id: UUID, course_id: UUID) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        latest_report = await self._latest_report(user_id, course_id)
        if latest_report is not None:
            for action in (latest_report.recommended_actions or [])[:5]:
                payloads.append(
                    {
                        "user_id": user_id,
                        "course_id": course_id,
                        "recommendation_type": str(action.get("action_type") or "diagnosis_action"),
                        "target_id": self._optional_uuid(action.get("target_id")),
                        "title": str(action.get("title") or "完成诊断建议"),
                        "reason": str(action.get("reason") or "基于最近诊断报告生成。"),
                        "priority": int(action.get("priority") or len(payloads) + 1),
                        "status": "pending",
                    }
                )

        path_items = await self._pending_path_items(user_id, course_id)
        for item in path_items[:5]:
            payloads.append(
                {
                    "user_id": user_id,
                    "course_id": course_id,
                    "recommendation_type": f"path_{item.item_type}",
                    "target_id": item.id,
                    "title": item.title,
                    "reason": item.reason or "来自当前学习路径的下一步任务。",
                    "priority": len(payloads) + 1,
                    "status": "pending",
                }
            )

        if not payloads:
            payloads.append(
                {
                    "user_id": user_id,
                    "course_id": course_id,
                    "recommendation_type": "practice",
                    "target_id": None,
                    "title": "完成一组数据结构练习",
                    "reason": "当前缺少诊断和路径证据，先通过练习积累推荐依据。",
                    "priority": 1,
                    "status": "pending",
                }
            )
        return payloads

    async def _latest_report(self, user_id: UUID, course_id: UUID) -> DiagnosisReport | None:
        result = await self.db.execute(
            select(DiagnosisReport)
            .where(DiagnosisReport.user_id == user_id, DiagnosisReport.course_id == course_id)
            .order_by(DiagnosisReport.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _pending_path_items(self, user_id: UUID, course_id: UUID) -> list[LearningPathItem]:
        result = await self.db.execute(
            select(LearningPathItem)
            .join(LearningPath, LearningPathItem.path_id == LearningPath.id)
            .where(
                LearningPath.user_id == user_id,
                LearningPath.course_id == course_id,
                LearningPathItem.status.in_(["pending", "doing"]),
            )
            .order_by(LearningPathItem.order_index.asc())
        )
        return list(result.scalars().all())

    async def _get_owned_recommendation(self, item_id: UUID, user_id: UUID) -> Recommendation:
        item = await self.db.get(Recommendation, item_id)
        if item is None or item.user_id != user_id:
            raise BusinessException(code=ErrorCode.NOT_FOUND, detail="推荐项不存在", status_code=404)
        return item

    def _serialize(self, item: Recommendation) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "user_id": str(item.user_id),
            "course_id": str(item.course_id),
            "recommendation_type": item.recommendation_type,
            "target_id": str(item.target_id) if item.target_id else None,
            "title": item.title,
            "reason": item.reason,
            "priority": item.priority,
            "strategy_version_id": str(item.strategy_version_id) if item.strategy_version_id else None,
            "status": item.status,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }

    def _optional_uuid(self, value: Any) -> UUID | None:
        if not value:
            return None
        try:
            return UUID(str(value))
        except (TypeError, ValueError):
            return None
