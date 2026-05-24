from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentRun


class AgentLogService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def start_run(
        self,
        *,
        task_type: str,
        agent_name: str,
        input_payload: dict[str, Any],
        user_id: UUID | None = None,
        course_id: UUID | None = None,
    ) -> AgentRun:
        run = AgentRun(
            user_id=user_id,
            course_id=course_id,
            task_type=task_type,
            agent_name=agent_name,
            input_payload=input_payload,
            output_payload={},
            status="running",
        )
        self.db.add(run)
        await self.db.flush()
        return run

    async def finish_run(
        self,
        *,
        run_id: UUID,
        output_payload: dict[str, Any],
        status: str,
        duration_ms: int,
        error_message: str | None = None,
    ) -> AgentRun:
        run = await self.db.get(AgentRun, run_id)
        if run is None:
            raise ValueError(f"AgentRun not found: {run_id}")
        run.output_payload = output_payload
        run.status = status
        run.duration_ms = duration_ms
        run.error_message = error_message
        await self.db.flush()
        return run

    async def list_runs(
        self,
        *,
        user_id: UUID | None = None,
        course_id: UUID | None = None,
        task_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AgentRun], int]:
        query = select(AgentRun)
        count_query = select(func.count()).select_from(AgentRun)

        if user_id is not None:
            query = query.where(AgentRun.user_id == user_id)
            count_query = count_query.where(AgentRun.user_id == user_id)
        if course_id is not None:
            query = query.where(AgentRun.course_id == course_id)
            count_query = count_query.where(AgentRun.course_id == course_id)
        if task_type is not None:
            query = query.where(AgentRun.task_type == task_type)
            count_query = count_query.where(AgentRun.task_type == task_type)
        if status is not None:
            query = query.where(AgentRun.status == status)
            count_query = count_query.where(AgentRun.status == status)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        query = query.order_by(AgentRun.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def get_run(self, run_id: UUID) -> AgentRun | None:
        return await self.db.get(AgentRun, run_id)
