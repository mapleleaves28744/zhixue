from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.memory import StudentMemory
from app.schemas.memory import MemoryRead, MemoryUpdate


class MemoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_memories(
        self,
        user_id: UUID,
        course_id: UUID | None = None,
        memory_type: str | None = None,
    ) -> list[MemoryRead]:
        stmt = select(StudentMemory).where(StudentMemory.user_id == user_id)
        if course_id is not None:
            stmt = stmt.where(StudentMemory.course_id == course_id)
        if memory_type is not None:
            stmt = stmt.where(StudentMemory.memory_type == memory_type)
        stmt = stmt.order_by(StudentMemory.created_at.desc())
        result = await self.db.execute(stmt)
        return [MemoryRead.model_validate(m) for m in result.scalars().all()]

    async def reflect(self, user_id: UUID, course_id: UUID | None = None) -> list[MemoryRead]:
        from app.agents.context import AgentContext
        from app.agents.memory_agent import MemoryAgent

        agent = MemoryAgent(self.db)
        context = AgentContext(
            user_id=user_id,
            course_id=course_id or user_id,
            task_type="memory_reflect",
            params={"action": "reflect", "course_id": str(course_id) if course_id else None},
        )
        result = await agent.run(context)
        if not result.success:
            raise BusinessException(
                code=ErrorCode.LLM_CALL_FAILED,
                detail=result.message,
                status_code=500,
            )
        return await self.list_memories(user_id, course_id)

    async def delete_memory(self, memory_id: UUID, user_id: UUID) -> None:
        stmt = select(StudentMemory).where(
            StudentMemory.id == memory_id,
            StudentMemory.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        memory = result.scalar_one_or_none()
        if memory is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="记忆不存在",
                status_code=404,
            )
        await self.db.delete(memory)
        await self.db.commit()

    async def update_memory(
        self, memory_id: UUID, user_id: UUID, payload: MemoryUpdate
    ) -> MemoryRead:
        stmt = select(StudentMemory).where(
            StudentMemory.id == memory_id,
            StudentMemory.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        memory = result.scalar_one_or_none()
        if memory is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="记忆不存在",
                status_code=404,
            )
        values = payload.model_dump(exclude_unset=True)
        for key, value in values.items():
            setattr(memory, key, value)
        await self.db.commit()
        await self.db.refresh(memory)
        return MemoryRead.model_validate(memory)
