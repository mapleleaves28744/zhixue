from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
import logging
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.agent_task import AgentTask, AgentTaskStep
from app.models.learning_path import LearningPath, LearningPathItem
from app.models.pet import PetNotification, PetPreference
from app.models.recommendation import Recommendation
from app.models.user import User
from app.schemas.pet import PetNotificationRead, PetPreferenceRead, PetPreferenceUpdate

logger = logging.getLogger(__name__)

RESOURCE_SECTION_LABELS = {
    "explanation": "讲解",
    "summary": "总结",
    "example": "例题",
    "flashcard": "复习卡",
    "review": "错题解析",
    "mindmap": "思维导图",
    "diagram": "图解",
    "image": "教学插图",
    "video": "讲解视频",
    "animation": "动画演示",
    "interactive_courseware": "互动课件",
    "code_project": "代码实操",
    "reading_pack": "拓展阅读",
}

RESOURCE_TYPE_ALIASES = {
    "courseware": "interactive_courseware",
    "interactive_classroom": "interactive_courseware",
    "immersive_classroom": "interactive_courseware",
    "narrated_classroom_video": "video",
    "storyboard": "video",
    "media_video": "video",
    "media_image": "image",
    "mermaid": "diagram",
}


class PetService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def feed(self, current_user: User) -> dict[str, object]:
        preference = await self._get_or_create_preference(current_user.id)
        await self._maybe_create_study_reminder(current_user.id, preference)
        items = list(
            (
                await self.db.execute(
                    select(PetNotification)
                    .where(PetNotification.user_id == current_user.id)
                    .order_by(PetNotification.is_read.asc(), PetNotification.created_at.desc())
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )
        await self.db.commit()
        return {
            "items": [PetNotificationRead.model_validate(item).model_dump(mode="json") for item in items],
            "unread_count": sum(not item.is_read for item in items),
        }

    async def mark_read(self, notification_id: UUID, current_user: User) -> PetNotificationRead:
        item = await self.db.get(PetNotification, notification_id)
        if item is None or item.user_id != current_user.id:
            raise BusinessException(code=ErrorCode.NOT_FOUND, detail="桌宠提醒不存在", status_code=404)
        item.is_read = True
        item.read_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(item)
        return PetNotificationRead.model_validate(item)

    async def mark_all_read(self, current_user: User) -> dict[str, int]:
        items = list(
            (
                await self.db.execute(
                    select(PetNotification).where(
                        PetNotification.user_id == current_user.id,
                        PetNotification.is_read.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )
        now = datetime.now(UTC)
        for item in items:
            item.is_read = True
            item.read_at = now
        await self.db.commit()
        return {"updated_count": len(items)}

    async def get_preferences(self, current_user: User) -> PetPreferenceRead:
        return PetPreferenceRead.model_validate(await self._get_or_create_preference(current_user.id))

    async def update_preferences(self, payload: PetPreferenceUpdate, current_user: User) -> PetPreferenceRead:
        preference = await self._get_or_create_preference(current_user.id)
        for key, value in payload.model_dump(exclude_none=True).items():
            setattr(preference, key, value)
        await self.db.commit()
        await self.db.refresh(preference)
        return PetPreferenceRead.model_validate(preference)

    async def create_agent_completion(self, task: AgentTask) -> None:
        resource_type = await self._infer_task_resource_type(task)
        await self.create_notification(
            user_id=task.user_id,
            course_id=task.course_id,
            notification_type="agent_completed",
            title="智能体任务已经完成",
            reason=self._completion_reason(task.task_goal, resource_type),
            source_type="agent_task",
            source_id=task.id,
            action_url=self.agent_action_url(task.course_id, task.conversation_id, task.id, resource_type=resource_type),
            dedupe_key=f"agent-task:{task.id}:completed",
        )

    async def safely_create_agent_completion(self, task: AgentTask) -> None:
        try:
            await self.create_agent_completion(task)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            logger.exception("pet agent completion notification failed task=%s", task.id)

    async def create_media_completion(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        job_id: UUID,
        title: str,
        conversation_id: UUID | None,
        agent_task_id: UUID | None,
        resource_type: str | None = None,
    ) -> None:
        normalized_type = self.normalize_resource_type(resource_type)
        action_url = (
            self.agent_action_url(course_id, conversation_id, agent_task_id, resource_type=normalized_type)
            if agent_task_id
            else self.agent_action_url(course_id, None, None, resource_type=normalized_type)
        )
        label = self.resource_section_label(normalized_type)
        await self.create_notification(
            user_id=user_id,
            course_id=course_id,
            notification_type="media_completed",
            title=title,
            reason=(
                f"个性化资源已生成完成，已放入「{label}」分类，可以返回查看。"
                if label
                else "个性化资源已生成完成，可以返回查看。"
            ),
            source_type="media_job",
            source_id=job_id,
            action_url=action_url,
            dedupe_key=f"media-job:{job_id}:completed",
        )

    async def safely_create_media_completion(self, **values) -> None:
        try:
            await self.create_media_completion(**values)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            logger.exception("pet media completion notification failed job=%s", values.get("job_id"))

    async def create_notification(self, **values) -> None:
        stmt = insert(PetNotification).values(**values).on_conflict_do_nothing(index_elements=["dedupe_key"])
        await self.db.execute(stmt)
        await self.db.flush()

    async def _get_or_create_preference(self, user_id: UUID) -> PetPreference:
        item = (
            await self.db.execute(select(PetPreference).where(PetPreference.user_id == user_id))
        ).scalar_one_or_none()
        if item is None:
            stmt = insert(PetPreference).values(user_id=user_id).on_conflict_do_nothing(index_elements=["user_id"])
            await self.db.execute(stmt)
            await self.db.flush()
            item = (
                await self.db.execute(select(PetPreference).where(PetPreference.user_id == user_id))
            ).scalar_one()
        return item

    async def _maybe_create_study_reminder(self, user_id: UUID, preference: PetPreference) -> None:
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        if not preference.study_reminders_enabled or self.is_quiet_time(now.time(), preference.quiet_start, preference.quiet_end):
            return
        if preference.last_study_reminder_at and now - preference.last_study_reminder_at < timedelta(hours=preference.interval_hours):
            return
        recommendation = (
            await self.db.execute(
                select(Recommendation)
                .where(Recommendation.user_id == user_id, Recommendation.status == "pending")
                .order_by(Recommendation.priority.asc(), Recommendation.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if recommendation:
            await self.create_notification(
                user_id=user_id,
                course_id=recommendation.course_id,
                notification_type="study_reminder",
                title=recommendation.title,
                reason=recommendation.reason,
                source_type="recommendation",
                source_id=recommendation.id,
                action_url=self._recommendation_action(recommendation),
                dedupe_key=f"study:recommendation:{recommendation.id}:{now.date().isoformat()}",
            )
            preference.last_study_reminder_at = now
            return
        path_item = (
            await self.db.execute(
                select(LearningPathItem)
                .join(LearningPath, LearningPathItem.path_id == LearningPath.id)
                .where(LearningPath.user_id == user_id, LearningPathItem.status.in_(["pending", "doing"]))
                .order_by(LearningPathItem.order_index.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if path_item:
            path = await self.db.get(LearningPath, path_item.path_id)
            await self.create_notification(
                user_id=user_id,
                course_id=path.course_id if path else None,
                notification_type="study_reminder",
                title=path_item.title,
                reason=path_item.reason or "来自当前学习路径的下一步任务。",
                source_type="learning_path_item",
                source_id=path_item.id,
                action_url="/path-profile",
                dedupe_key=f"study:path-item:{path_item.id}:{now.date().isoformat()}",
            )
            preference.last_study_reminder_at = now

    @staticmethod
    def is_quiet_time(current: time, quiet_start: time, quiet_end: time) -> bool:
        if quiet_start <= quiet_end:
            return quiet_start <= current < quiet_end
        return current >= quiet_start or current < quiet_end

    @staticmethod
    def agent_action_url(
        course_id: UUID,
        conversation_id: UUID | None,
        task_id: UUID | None,
        *,
        resource_type: str | None = None,
    ) -> str:
        parts = [f"course_id={course_id}"]
        if conversation_id:
            parts.append(f"conversation_id={conversation_id}")
        if task_id:
            parts.append(f"task_id={task_id}")
        normalized_type = PetService.normalize_resource_type(resource_type)
        if normalized_type:
            parts.append(f"resource_type={normalized_type}")
        return f"/assistant?{'&'.join(parts)}"

    @staticmethod
    def normalize_resource_type(value: str | None) -> str | None:
        if not value:
            return None
        raw = str(value).strip()
        if raw in RESOURCE_SECTION_LABELS:
            return raw
        return RESOURCE_TYPE_ALIASES.get(raw)

    @staticmethod
    def resource_section_label(value: str | None) -> str | None:
        normalized = PetService.normalize_resource_type(value)
        return RESOURCE_SECTION_LABELS.get(normalized) if normalized else None

    @classmethod
    def _completion_reason(cls, task_goal: str, resource_type: str | None) -> str:
        label = cls.resource_section_label(resource_type)
        goal = task_goal[:240] if label else task_goal[:300]
        if not label:
            return goal
        return f"{goal}；生成产物已放入「{label}」分类。"

    async def _infer_task_resource_type(self, task: AgentTask) -> str | None:
        payloads = [task.plan_json, task.input_payload, task.intent_payload]
        for payload in payloads:
            inferred = self._resource_type_from_payload(payload)
            if inferred:
                return inferred
        steps = list(
            (
                await self.db.execute(
                    select(AgentTaskStep)
                    .where(AgentTaskStep.task_id == task.id)
                    .order_by(AgentTaskStep.step_index.desc())
                )
            )
            .scalars()
            .all()
        )
        for step in steps:
            inferred = self._resource_type_from_payload(step.artifact_refs) or self._resource_type_from_payload(
                step.output_payload
            )
            if inferred:
                return inferred
        return None

    @classmethod
    def _resource_type_from_payload(cls, payload: object, depth: int = 0) -> str | None:
        if depth > 4:
            return None
        if isinstance(payload, list):
            for item in payload:
                inferred = cls._resource_type_from_payload(item, depth + 1)
                if inferred:
                    return inferred
            return None
        if not isinstance(payload, dict):
            return None
        for key in ("resource_type", "subtype", "asset_type", "preview_mode"):
            inferred = cls.normalize_resource_type(payload.get(key))
            if inferred:
                return inferred
        for key in ("artifact_refs", "artifacts", "output", "result"):
            inferred = cls._resource_type_from_payload(payload.get(key), depth + 1)
            if inferred:
                return inferred
        return None

    @staticmethod
    def _recommendation_action(item: Recommendation) -> str:
        if "practice" in item.recommendation_type or "quiz" in item.recommendation_type:
            return f"/practice?course_id={item.course_id}"
        return f"/path-profile?course_id={item.course_id}"
