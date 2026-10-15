from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.memory_retrieval_service import MemoryRetrievalService


def _memory(content: str, *, salience: str, memory_type: str = "insight") -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid4(), user_id=uuid4(), course_id=uuid4(),
        memory_type=memory_type, memory_key=content,
        content=content, evidence=[], confidence=Decimal("0.8"),
        status="active", salience=Decimal(salience), reinforcement_count=1,
        last_reinforced_at=now, archived_at=None, created_at=now, updated_at=now,
    )


@pytest.mark.asyncio
async def test_relevant_memory_survives_more_than_fifty_high_salience_candidates() -> None:
    user_id, course_id = uuid4(), uuid4()
    irrelevant = [_memory(f"关注数据库索引概念 {index}", salience="0.99") for index in range(55)]
    relevant = _memory("曾混淆递归终止条件和递归调用", salience="0.10")
    relevant.course_id = course_id

    class Result:
        def scalars(self):
            return self

        def all(self):
            return [*irrelevant, relevant]

    class DB:
        async def execute(self, statement):
            return Result()

    recalled = await MemoryRetrievalService(DB()).retrieve(  # type: ignore[arg-type]
        user_id=user_id, course_id=course_id, question="递归终止条件为什么重要", limit=5,
    )

    assert [memory.id for memory in recalled] == [relevant.id]
