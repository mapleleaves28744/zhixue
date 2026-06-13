from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.memory import StudentMemory
from app.schemas.memory import MemoryHealth, MemoryRead, MemoryUpdate


class MemoryService:
    COURSE_CAPACITY = 20
    GLOBAL_CAPACITY = 10

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_memories(
        self,
        user_id: UUID,
        course_id: UUID | None = None,
        memory_type: str | None = None,
        status: str = "active",
        limit: int | None = None,
    ) -> list[MemoryRead]:
        stmt = select(StudentMemory).where(StudentMemory.user_id == user_id)
        if course_id is not None:
            stmt = stmt.where(StudentMemory.course_id == course_id)
        if memory_type is not None:
            stmt = stmt.where(StudentMemory.memory_type == memory_type)
        if status != "all":
            stmt = stmt.where(StudentMemory.status == status)
        stmt = stmt.order_by(
            StudentMemory.salience.desc(),
            StudentMemory.confidence.desc(),
            StudentMemory.last_reinforced_at.desc().nullslast(),
            StudentMemory.updated_at.desc(),
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        return [MemoryRead.model_validate(m) for m in result.scalars().all()]

    @classmethod
    def build_memory_key(cls, memory_type: str, content: str) -> str:
        normalized = re.sub(r"\s+", " ", content.strip().lower())
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
        return f"{memory_type}:{digest}"

    @classmethod
    def active_capacity(cls, course_id: object | None) -> int:
        return cls.COURSE_CAPACITY if course_id is not None else cls.GLOBAL_CAPACITY

    async def upsert_memory(
        self,
        *,
        user_id: UUID,
        course_id: UUID | None,
        memory_type: str,
        content: str,
        evidence: list[Any],
        confidence: float,
        salience: float | None = None,
    ) -> tuple[StudentMemory, str]:
        key = self.build_memory_key(memory_type, content)
        condition = [
            StudentMemory.user_id == user_id,
            StudentMemory.memory_key == key,
        ]
        condition.append(StudentMemory.course_id == course_id if course_id is not None else StudentMemory.course_id.is_(None))
        existing = (await self.db.execute(
            select(StudentMemory).where(*condition).order_by(
                (StudentMemory.status == "active").desc(),
                StudentMemory.confidence.desc(),
                StudentMemory.updated_at.desc(),
            ).limit(1)
        )).scalar_one_or_none()
        now = datetime.now(UTC)
        if existing is not None:
            existing.evidence = self._merge_evidence(existing.evidence or [], evidence)
            existing.confidence = max(float(existing.confidence), confidence)
            existing.salience = max(float(existing.salience), salience if salience is not None else confidence)
            existing.reinforcement_count += 1
            existing.last_reinforced_at = now
            existing.status = "active"
            existing.archived_at = None
            action = "reinforce"
            memory = existing
        else:
            memory = StudentMemory(
                user_id=user_id,
                course_id=course_id,
                memory_type=memory_type,
                memory_key=key,
                content=content,
                evidence=evidence,
                confidence=confidence,
                salience=salience if salience is not None else confidence,
                last_reinforced_at=now,
            )
            self.db.add(memory)
            action = "add"
        await self.db.flush()
        await self.enforce_capacity(user_id=user_id, course_id=course_id)
        return memory, action

    async def enforce_capacity(self, *, user_id: UUID, course_id: UUID | None) -> None:
        condition = [StudentMemory.user_id == user_id, StudentMemory.status == "active"]
        condition.append(StudentMemory.course_id == course_id if course_id is not None else StudentMemory.course_id.is_(None))
        rows = list((await self.db.execute(select(StudentMemory).where(*condition).order_by(
            StudentMemory.salience.desc(), StudentMemory.confidence.desc(), StudentMemory.updated_at.desc()
        ))).scalars().all())
        now = datetime.now(UTC)
        for item in rows[self.active_capacity(course_id):]:
            item.status = "archived"
            item.archived_at = now

    async def health(self, user_id: UUID, course_id: UUID | None) -> MemoryHealth:
        condition = [StudentMemory.user_id == user_id]
        condition.append(StudentMemory.course_id == course_id if course_id is not None else StudentMemory.course_id.is_(None))
        rows = (await self.db.execute(select(StudentMemory.status, func.count()).where(*condition).group_by(StudentMemory.status))).all()
        counts = {str(status): int(count) for status, count in rows}
        capacity = self.active_capacity(course_id)
        active = counts.get("active", 0)
        return MemoryHealth(active_count=active, archived_count=counts.get("archived", 0), capacity=capacity, remaining=max(0, capacity - active))

    async def restore_memory(self, memory_id: UUID, user_id: UUID) -> MemoryRead:
        memory = await self._get_owned(memory_id, user_id)
        memory.status = "active"
        memory.archived_at = None
        memory.last_reinforced_at = datetime.now(UTC)
        await self.enforce_capacity(user_id=user_id, course_id=memory.course_id)
        await self.db.commit()
        await self.db.refresh(memory)
        return MemoryRead.model_validate(memory)

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
        memory = await self._get_owned(memory_id, user_id)
        memory.status = "archived"
        memory.archived_at = datetime.now(UTC)
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

    async def _get_owned(self, memory_id: UUID, user_id: UUID) -> StudentMemory:
        result = await self.db.execute(select(StudentMemory).where(StudentMemory.id == memory_id, StudentMemory.user_id == user_id))
        memory = result.scalar_one_or_none()
        if memory is None:
            raise BusinessException(code=ErrorCode.NOT_FOUND, detail="记忆不存在", status_code=404)
        return memory

    def _merge_evidence(self, existing: list[Any], incoming: list[Any]) -> list[Any]:
        merged: list[Any] = []
        seen: set[str] = set()
        for item in existing + incoming:
            key = repr(item)
            if key not in seen:
                seen.add(key)
                merged.append(item)
        return merged[-20:]
