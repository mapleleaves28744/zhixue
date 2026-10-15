from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import StudentMemory
from app.schemas.memory import MemoryRead
from app.services.memory_facts import normalize_fact_text


def _terms(value: str) -> set[str]:
    text = value.lower()
    words = set(re.findall(r"[a-z][a-z0-9_]{1,}|\d+", text))
    chinese = re.findall(r"[\u4e00-\u9fff]+", text)
    return words | {part[index:index + 2] for part in chinese for index in range(len(part) - 1)}


class MemoryRetrievalService:
    """Recall active memories in the current course and global scope before applying prompt limits."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def retrieve(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        question: str,
        limit: int = 5,
    ) -> list[MemoryRead]:
        statement = select(StudentMemory).where(
            StudentMemory.user_id == user_id,
            StudentMemory.status == "active",
            or_(
                StudentMemory.course_id == course_id,
                (
                    StudentMemory.course_id.is_(None)
                    & (StudentMemory.lifecycle_meta["scope"].astext == "global")
                ),
            ),
        )
        memories = list((await self.db.execute(statement.execution_options(populate_existing=True))).scalars().all())
        now = datetime.now(UTC)
        valid = []
        for memory in memories:
            expiry = (getattr(memory, "lifecycle_meta", {}) or {}).get("valid_until")
            if expiry:
                try:
                    until = datetime.fromisoformat(str(expiry).replace("Z", "+00:00"))
                    if until.tzinfo is None:
                        until = until.replace(tzinfo=UTC)
                    if until <= now:
                        continue
                except ValueError:
                    continue
            valid.append(memory)
        # A course-specific version overrides the same global fact in this course.
        by_fact = {}
        for memory in sorted(valid, key=lambda item: item.course_id == course_id):
            key = getattr(memory, "fact_key", None) or f"{memory.memory_type}:{normalize_fact_text(memory.content)}"
            by_fact[key] = memory
        memories = list(by_fact.values())
        query_terms = _terms(question)
        memories = [
            memory for memory in memories
            if memory.memory_type == "preference" or bool(query_terms & _terms(memory.content))
        ]

        def rank(memory: StudentMemory) -> tuple[float, float, float]:
            content_terms = _terms(memory.content)
            relevance = len(query_terms & content_terms) / max(len(query_terms), 1)
            course_bonus = 0.05 if memory.course_id == course_id else 0.0
            preference_bonus = 0.15 if memory.memory_type == "preference" else 0.0
            return (relevance + course_bonus + preference_bonus, float(memory.salience), float(memory.confidence))

        memories.sort(key=rank, reverse=True)
        selected: list[MemoryRead] = []
        remaining_chars = 1500
        for memory in memories[:limit]:
            if remaining_chars <= 0:
                break
            content = memory.content[:min(250, remaining_chars)]
            remaining_chars -= len(content)
            selected.append(MemoryRead.model_validate(memory).model_copy(update={
                "content": content,
                "evidence": list(memory.evidence or [])[:3],
                "selection_reason": "回答风格偏好" if memory.memory_type == "preference" else "与当前问题词项相关",
            }))
        return selected
