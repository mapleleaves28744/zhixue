from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.context import AgentContext
from app.agents.orchestrator import OrchestratorAgent
from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.course import Course
from app.models.knowledge import KnowledgePoint
from app.models.learning_path import LearningPath, LearningPathItem
from app.models.profile import StudentProfile
from app.models.user import User
from app.models.wiki import WikiPage
from app.schemas.learning_path import (
    LearningPathGenerateRequest,
    LearningPathItemRead,
    LearningPathItemUpdate,
    LearningPathRead,
)
from app.services.course_service import CourseService


class LearningPathService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_paths(
        self,
        *,
        current_user: User,
        course_id: UUID | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[LearningPathRead], int]:
        stmt = (
            select(LearningPath)
            .where(LearningPath.user_id == current_user.id)
            .options(selectinload(LearningPath.items))
        )
        if course_id is not None:
            stmt = stmt.where(LearningPath.course_id == course_id)
        if status is not None:
            stmt = stmt.where(LearningPath.status == status)

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(total_stmt)).scalar() or 0
        stmt = stmt.order_by(LearningPath.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        paths = result.scalars().unique().all()
        return [LearningPathRead.model_validate(path) for path in paths], total

    async def get_path(self, path_id: UUID, current_user: User) -> LearningPathRead:
        path = await self._get_owned_path(path_id, current_user.id)
        return LearningPathRead.model_validate(path)

    async def generate(
        self,
        *,
        payload: LearningPathGenerateRequest,
        current_user: User,
    ) -> LearningPathRead:
        await CourseService(self.db)._get_accessible_course(payload.course_id, current_user)

        knowledge_points = await self._list_knowledge_points(payload.course_id)
        if not knowledge_points:
            knowledge_points = self._default_data_structure_points(payload.course_id)

        profile = await self._get_profile(current_user.id)
        wiki_lookup = await self._build_wiki_lookup(payload.course_id, current_user.id)

        orchestrator = OrchestratorAgent(self.db)
        agent_result = await orchestrator.run(
            AgentContext(
                user_id=current_user.id,
                course_id=payload.course_id,
                task_type="plan_learning",
                params={
                    "learning_goal": payload.goal,
                    "path_type": payload.path_type,
                    "target_knowledge_ids": [str(item) for item in payload.target_knowledge_ids],
                    "student_profile": self._profile_summary(profile),
                    "weak_points": profile.weak_points if profile else [],
                    "mastery_snapshot": profile.mastery_snapshot if profile else {},
                    "knowledge_points": [self._knowledge_payload(point) for point in knowledge_points],
                },
            )
        )
        if not agent_result.success:
            raise BusinessException(
                code=ErrorCode.AGENT_RUN_FAILED,
                detail=agent_result.message,
                status_code=500,
            )

        plan_items = agent_result.data.get("items") or []
        if not plan_items:
            plan_items = self._rule_plan_items(
                goal=payload.goal,
                target_knowledge_ids=payload.target_knowledge_ids,
                weak_points=profile.weak_points if profile else [],
                mastery_snapshot=profile.mastery_snapshot if profile else {},
                knowledge_points=knowledge_points,
            )

        title = self._make_title(payload.goal, payload.path_type)
        path = LearningPath(
            user_id=current_user.id,
            course_id=payload.course_id,
            title=title,
            goal=payload.goal,
            reason=agent_result.data.get("reason") or self._default_reason(profile, payload.goal),
            status="active",
            progress=Decimal("0"),
        )
        self.db.add(path)
        await self.db.flush()

        knowledge_by_id = {str(point.id): point for point in knowledge_points}
        for index, item in enumerate(plan_items[:8], start=1):
            knowledge_id = item.get("knowledge_id")
            knowledge = knowledge_by_id.get(str(knowledge_id)) if knowledge_id else None
            title_value = item.get("title") or (f"学习 {knowledge.name}" if knowledge else f"路径节点 {index}")
            wiki_page = wiki_lookup.get((knowledge.name if knowledge else title_value).lower())
            self.db.add(
                LearningPathItem(
                    path_id=path.id,
                    knowledge_id=knowledge.id if knowledge else None,
                    wiki_page_id=wiki_page.id if wiki_page else None,
                    title=title_value,
                    item_type=item.get("item_type") or self._item_type_for_index(index),
                    order_index=index,
                    status="doing" if index == 1 else "pending",
                    reason=item.get("reason") or "基于目标、薄弱点和知识点顺序生成。",
                    estimated_minutes=int(item.get("estimated_minutes") or 30),
                )
            )

        await self.db.commit()
        return await self.get_path(path.id, current_user)

    async def update_item(
        self,
        *,
        item_id: UUID,
        payload: LearningPathItemUpdate,
        current_user: User,
    ) -> LearningPathItemRead:
        stmt = (
            select(LearningPathItem)
            .join(LearningPath, LearningPath.id == LearningPathItem.path_id)
            .where(LearningPathItem.id == item_id, LearningPath.user_id == current_user.id)
            .options(selectinload(LearningPathItem.path))
        )
        result = await self.db.execute(stmt)
        item = result.scalar_one_or_none()
        if item is None:
            raise BusinessException(code=ErrorCode.NOT_FOUND, detail="路径节点不存在", status_code=404)

        item.status = payload.status
        item.completed_at = datetime.now(UTC) if payload.status == "completed" else None
        await self.db.flush()
        await self._refresh_progress(item.path_id)
        await self.db.commit()
        await self.db.refresh(item)
        return LearningPathItemRead.model_validate(item)

    async def archive_path(self, path_id: UUID, current_user: User) -> LearningPathRead:
        path = await self._get_owned_path(path_id, current_user.id)
        path.status = "archived"
        await self.db.commit()
        await self.db.refresh(path)
        return LearningPathRead.model_validate(path)

    async def _get_owned_path(self, path_id: UUID, user_id: UUID) -> LearningPath:
        stmt = (
            select(LearningPath)
            .where(LearningPath.id == path_id, LearningPath.user_id == user_id)
            .options(selectinload(LearningPath.items))
        )
        result = await self.db.execute(stmt)
        path = result.scalars().unique().one_or_none()
        if path is None:
            raise BusinessException(code=ErrorCode.NOT_FOUND, detail="学习路径不存在", status_code=404)
        return path

    async def _refresh_progress(self, path_id: UUID) -> None:
        result = await self.db.execute(select(LearningPathItem).where(LearningPathItem.path_id == path_id))
        items = result.scalars().all()
        completed = sum(1 for item in items if item.status == "completed")
        progress = Decimal("0") if not items else Decimal(completed * 100) / Decimal(len(items))
        path = await self.db.get(LearningPath, path_id)
        if path:
            path.progress = progress.quantize(Decimal("0.01"))
            path.status = "completed" if items and completed == len(items) else "active"

    async def _list_knowledge_points(self, course_id: UUID) -> list[KnowledgePoint]:
        result = await self.db.execute(
            select(KnowledgePoint).where(KnowledgePoint.course_id == course_id).order_by(KnowledgePoint.sort_order, KnowledgePoint.name)
        )
        return list(result.scalars().all())

    async def _get_profile(self, user_id: UUID) -> StudentProfile | None:
        result = await self.db.execute(select(StudentProfile).where(StudentProfile.user_id == user_id))
        return result.scalar_one_or_none()

    async def _build_wiki_lookup(self, course_id: UUID, user_id: UUID) -> dict[str, WikiPage]:
        result = await self.db.execute(
            select(WikiPage).where(WikiPage.course_id == course_id, WikiPage.owner_id == user_id, WikiPage.status == "active")
        )
        pages = result.scalars().all()
        return {page.title.lower(): page for page in pages}

    def _rule_plan_items(
        self,
        *,
        goal: str,
        target_knowledge_ids: list[UUID],
        weak_points: list[Any],
        mastery_snapshot: dict[str, Any],
        knowledge_points: list[KnowledgePoint],
    ) -> list[dict[str, Any]]:
        target_ids = {str(item) for item in target_knowledge_ids}
        weak_names = {str(item.get("name", item)).lower() for item in weak_points if item}

        def score(point: KnowledgePoint) -> tuple[int, float, int, str]:
            mastery = self._mastery_for(point, mastery_snapshot)
            target_bonus = 0 if str(point.id) in target_ids else 1
            weak_bonus = 0 if point.name.lower() in weak_names or point.name in goal else 1
            return (target_bonus, weak_bonus, mastery, point.sort_order, point.name)

        selected = sorted(knowledge_points, key=score)[:5]
        if not selected:
            return []
        items: list[dict[str, Any]] = []
        for index, point in enumerate(selected, start=1):
            mastery = self._mastery_for(point, mastery_snapshot)
            items.append(
                {
                    "knowledge_id": str(point.id),
                    "title": f"{self._item_action(index)}：{point.name}",
                    "item_type": self._item_type_for_index(index),
                    "reason": f"当前掌握度约 {mastery}%；按先修顺序与薄弱点优先规则安排。",
                    "estimated_minutes": 25 + index * 5,
                }
            )
        return items

    def _default_data_structure_points(self, course_id: UUID) -> list[KnowledgePoint]:
        names = ["复杂度分析", "线性表", "栈与队列", "树与二叉树", "图的遍历"]
        return [
            KnowledgePoint(course_id=course_id, name=name, sort_order=index, difficulty="medium", importance="high")
            for index, name in enumerate(names, start=1)
        ]

    def _knowledge_payload(self, point: KnowledgePoint) -> dict[str, Any]:
        return {
            "id": str(point.id) if point.id else "",
            "name": point.name,
            "description": point.description,
            "difficulty": point.difficulty,
            "importance": point.importance,
            "sort_order": point.sort_order,
        }

    def _profile_summary(self, profile: StudentProfile | None) -> str:
        if profile is None:
            return "暂无画像，使用课程知识点顺序和目标生成路径。"
        parts = [profile.profile_summary or "画像摘要待积累"]
        if profile.weak_points:
            parts.append(f"薄弱点：{profile.weak_points}")
        if profile.mastery_snapshot:
            parts.append(f"掌握度快照：{profile.mastery_snapshot}")
        return "\n".join(parts)

    def _default_reason(self, profile: StudentProfile | None, goal: str) -> str:
        if profile and profile.weak_points:
            return f"围绕“{goal}”，优先补强画像中记录的薄弱点，并按知识点顺序安排复习、学习和练习。"
        return f"围绕“{goal}”，基于课程知识点顺序生成可执行路径，后续会随练习诊断继续调整。"

    def _make_title(self, goal: str, path_type: str) -> str:
        prefix = "补弱路径" if path_type == "weakness_repair" else "学习路径"
        return f"{goal[:24]} · {prefix}"

    def _mastery_for(self, point: KnowledgePoint, snapshot: dict[str, Any]) -> int:
        value = snapshot.get(str(point.id), snapshot.get(point.name, 60))
        try:
            number = float(value)
            if number <= 1:
                number *= 100
            return max(0, min(100, int(number)))
        except (TypeError, ValueError):
            return 60

    def _item_type_for_index(self, index: int) -> str:
        return ["review", "learn", "practice", "summary"][min(index - 1, 3)]

    def _item_action(self, index: int) -> str:
        return ["复习", "学习", "练习", "总结"][min(index - 1, 3)]
