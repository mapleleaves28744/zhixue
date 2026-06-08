from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_task import AgentTask, AgentTaskStep
from app.schemas.agent_task import AgentTaskPlan


class AgentTaskRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_orphaned_queued_tasks(self, *, limit: int = 20) -> list[AgentTask]:
        result = await self.db.execute(
            select(AgentTask)
            .where(
                AgentTask.status == "queued",
                AgentTask.started_at.is_(None),
                AgentTask.runtime_mode == "langgraph",
            )
            .order_by(AgentTask.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create_task(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        user_input: str,
        intent: dict[str, Any],
        plan: AgentTaskPlan,
        status: str,
    ) -> AgentTask:
        task = AgentTask(
            user_id=user_id,
            course_id=course_id,
            task_goal=plan.goal,
            task_type=str(intent["task_type"]),
            status=status,
            plan_schema_version=plan.plan_schema_version,
            plan_json=plan.model_dump(mode="json"),
            input_payload={"user_input": user_input},
            intent_payload=intent,
            risk_level=plan.risk_level,
            requires_confirmation=plan.requires_confirmation,
        )
        self.db.add(task)
        await self.db.flush()
        for plan_step in plan.steps:
            self.db.add(
                AgentTaskStep(
                    task_id=task.id,
                    step_index=plan_step.step,
                    agent_name=plan_step.agent,
                    skill_name=plan_step.skill,
                    action=plan_step.action,
                    expected_output=plan_step.expected_output,
                    status="pending",
                    input_payload=plan_step.input,
                )
            )
        await self.db.flush()
        await self.db.refresh(task)
        return task

    async def get_for_user(self, task_id: UUID, user_id: UUID) -> AgentTask | None:
        result = await self.db.execute(
            select(AgentTask).where(AgentTask.id == task_id, AgentTask.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, task_id: UUID) -> AgentTask | None:
        return await self.db.get(AgentTask, task_id)

    async def create_dynamic_task(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        conversation_id: UUID,
        thread_id: str,
        goal: str,
    ) -> AgentTask:
        task = AgentTask(
            user_id=user_id,
            course_id=course_id,
            conversation_id=conversation_id,
            thread_id=thread_id,
            task_goal=goal,
            task_type="dynamic_learning_agent",
            status="queued",
            plan_schema_version="2.0",
            graph_version="langgraph-1.0",
            runtime_mode="langgraph",
            plan_json={},
            input_payload={"user_input": goal},
            intent_payload={"source": "unified_agent"},
            risk_level="low",
            requires_confirmation=False,
        )
        self.db.add(task)
        await self.db.flush()
        return task

    async def get_step_by_tool_call(
        self,
        task_id: UUID,
        tool_call_id: str,
    ) -> AgentTaskStep | None:
        result = await self.db.execute(
            select(AgentTaskStep).where(
                AgentTaskStep.task_id == task_id,
                AgentTaskStep.tool_call_id == tool_call_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_dynamic_step(
        self,
        *,
        task_id: UUID,
        step_index: int,
        agent_name: str,
        action: str,
        tool_call_id: str,
        iteration_no: int,
        status: str,
        input_payload: dict[str, Any],
        output_payload: dict[str, Any],
        evidence: list[Any],
        artifact_refs: list[Any],
        error_message: str | None,
        retry_count: int,
        decision_summary: str | None = None,
    ) -> AgentTaskStep:
        step = AgentTaskStep(
            task_id=task_id,
            step_index=step_index,
            agent_name=agent_name,
            action=action,
            tool_call_id=tool_call_id,
            iteration_no=iteration_no,
            node_name="execute_tool",
            status=status,
            input_payload=input_payload,
            output_payload=output_payload,
            evidence=evidence,
            artifact_refs=artifact_refs,
            error_message=error_message,
            retry_count=retry_count,
            decision_summary=decision_summary,
        )
        self.db.add(step)
        await self.db.flush()
        return step

    async def list_steps(self, task_id: UUID) -> list[AgentTaskStep]:
        result = await self.db.execute(
            select(AgentTaskStep)
            .where(AgentTaskStep.task_id == task_id)
            .order_by(AgentTaskStep.step_index)
        )
        return list(result.scalars().all())

    async def update_task(self, task: AgentTask, **values: Any) -> AgentTask:
        for key, value in values.items():
            setattr(task, key, value)
        await self.db.flush()
        return task

    async def update_step(self, step: AgentTaskStep, **values: Any) -> AgentTaskStep:
        for key, value in values.items():
            setattr(step, key, value)
        await self.db.flush()
        return step

    async def skip_pending_steps(self, task_id: UUID, error_message: str) -> None:
        for step in await self.list_steps(task_id):
            if step.status == "pending":
                step.status = "skipped"
                step.error_message = error_message
        await self.db.flush()
