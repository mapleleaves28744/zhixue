from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context import AgentContext, AgentResult
from app.agents.orchestrator import OrchestratorAgent


class AgentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def run_task(
        self,
        *,
        task_type: str,
        user_id: UUID,
        course_id: UUID,
        params: dict | None = None,
    ) -> AgentResult:
        context = AgentContext(
            user_id=user_id,
            course_id=course_id,
            task_type=task_type,
            params=params or {},
        )
        orchestrator = OrchestratorAgent(db=self.db)
        return await orchestrator.run(context)
