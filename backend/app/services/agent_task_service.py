from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_graphs.learning_task_graph import LearningTaskGraph
from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.agent_task import AgentTask
from app.models.user import User
from app.repositories.agent_task_repository import AgentTaskRepository
from app.schemas.agent_task import (
    AgentTaskCreateRequest,
    AgentTaskRead,
    AgentTaskStepRead,
    build_task_plan,
)
from app.services.agent_service import AgentService
from app.services.course_service import CourseService


class AgentTaskService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.tasks = AgentTaskRepository(db)

    async def create_task(
        self,
        *,
        payload: AgentTaskCreateRequest,
        current_user: User,
    ) -> AgentTaskRead:
        await CourseService(self.db).get_readable_course(payload.course_id, current_user)
        result = await AgentService(self.db).run_task(
            task_type="route_intent",
            user_id=current_user.id,
            course_id=payload.course_id,
            params={"user_input": payload.user_input},
        )
        if not result.success:
            raise BusinessException(
                code=ErrorCode.AGENT_RUN_FAILED,
                detail=result.message,
                status_code=500,
            )
        plan = build_task_plan(result.data)
        status = "waiting_confirmation" if plan.requires_confirmation else "planned"
        task = await self.tasks.create_task(
            user_id=current_user.id,
            course_id=payload.course_id,
            user_input=payload.user_input,
            intent=result.data,
            plan=plan,
            status=status,
        )
        await self.db.commit()
        await self.db.refresh(task)
        return AgentTaskRead.model_validate(task)

    async def get_task(self, task_id: UUID, current_user: User) -> AgentTaskRead:
        return AgentTaskRead.model_validate(await self._get_owned_task(task_id, current_user.id))

    async def get_steps(self, task_id: UUID, current_user: User) -> list[AgentTaskStepRead]:
        task = await self._get_owned_task(task_id, current_user.id)
        return [AgentTaskStepRead.model_validate(item) for item in await self.tasks.list_steps(task.id)]

    async def confirm_task(self, task_id: UUID, current_user: User) -> AgentTaskRead:
        task = await self._get_owned_task(task_id, current_user.id)
        if task.status != "waiting_confirmation":
            raise BusinessException(
                code=ErrorCode.CONFLICT,
                detail="只有 waiting_confirmation 状态的任务可以确认",
                status_code=409,
            )
        await self.tasks.update_task(task, status="planned", confirmed_at=datetime.now(UTC))
        await self.db.commit()
        await self.db.refresh(task)
        return AgentTaskRead.model_validate(task)

    async def cancel_task(self, task_id: UUID, current_user: User) -> AgentTaskRead:
        task = await self._get_owned_task(task_id, current_user.id)
        self.ensure_can_cancel(task)
        await self.tasks.update_task(
            task,
            status="cancelled",
            cancelled_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )
        await self.tasks.skip_pending_steps(task.id, "任务已取消")
        await self.db.commit()
        await self.db.refresh(task)
        return AgentTaskRead.model_validate(task)

    async def run_task(self, task_id: UUID, current_user: User) -> AgentTaskRead:
        task = await self._get_owned_task(task_id, current_user.id)
        self.ensure_can_run(task)
        await LearningTaskGraph(self.db, repository=self.tasks).run(
            task=task,
            current_user=current_user,
        )
        await self.db.refresh(task)
        return AgentTaskRead.model_validate(task)

    def ensure_can_run(self, task: object) -> None:
        if getattr(task, "status", None) != "planned":
            raise BusinessException(
                code=ErrorCode.CONFLICT,
                detail="只有 planned 状态的任务可以执行",
                status_code=409,
            )

    async def _get_owned_task(self, task_id: UUID, user_id: UUID) -> AgentTask:
        task = await self.tasks.get_for_user(task_id, user_id)
        if task is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="Agent 任务不存在",
                status_code=404,
            )
        return task
    def ensure_can_cancel(self, task: object) -> None:
        if getattr(task, "status", None) not in {"planned", "waiting_confirmation", "running"}:
            raise BusinessException(
                code=ErrorCode.CONFLICT,
                detail="当前任务状态不可取消",
                status_code=409,
            )
