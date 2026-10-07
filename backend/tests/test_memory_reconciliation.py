from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.models.memory import StudentMemory
from app.services.memory_service import MemoryService
from app.repositories.memory_repository import MemoryRepository


def memory(content, status="active"):
    return StudentMemory(id=uuid4(), user_id=uuid4(), course_id=uuid4(), memory_type="preference",
                         memory_key=MemoryService.build_memory_key("preference", content), content=content,
                         fact_key=MemoryService.build_fact_key("preference", content, "legacy"),
                         status=status, evidence=[], confidence=0.8, salience=0.5, revision=1,
                         reinforcement_count=1, lifecycle_meta={}, origin="reflection",
                         created_at=datetime.now(UTC), updated_at=datetime.now(UTC))


def service_for(monkeypatch, rows, exact=None):
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: exact)),
                         flush=AsyncMock(), add=Mock())
    monkeypatch.setattr(MemoryRepository, "reconciliation_candidates", AsyncMock(return_value=rows))
    service = MemoryService(db)
    service._record_change = AsyncMock()
    service._advance_revision = AsyncMock()
    service.enforce_capacity = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_synonymous_candidate_cannot_recreate_forgotten_preference(monkeypatch):
    old = memory("学生喜欢用图解释", "forgotten")
    service = service_for(monkeypatch, [old])
    result, action = await service.upsert_memory(user_id=old.user_id, course_id=old.course_id,
        memory_type="preference", content="学生希望通过示意图学习", evidence=[str(uuid4())], confidence=0.95)
    assert result is old and action == "skipped"
    service.db.add.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_paraphrase_of_forgotten_preference_is_quarantined(monkeypatch):
    old = memory("学生喜欢用图解释", "forgotten")
    service = service_for(monkeypatch, [old])
    result, action = await service.upsert_memory(user_id=old.user_id, course_id=old.course_id,
        memory_type="preference", content="我倾向空间化理解教学内容", evidence=[str(uuid4())], confidence=0.9)
    assert action == "pending" and result.status == "pending"
    assert result.lifecycle_meta["review_reason"] == "possible_forgotten_fact"
    assert old.status == "forgotten"


@pytest.mark.asyncio
async def test_same_source_does_not_raise_confidence_or_reinforcement(monkeypatch):
    old = memory("学生喜欢用图解释")
    old.evidence = [str(uuid4())]
    service = service_for(monkeypatch, [old], old)
    _, action = await service.upsert_memory(user_id=old.user_id, course_id=old.course_id,
        memory_type="preference", content=old.content, evidence=old.evidence, confidence=0.99)
    assert action == "skipped"
    assert old.reinforcement_count == 1 and old.confidence == 0.8


@pytest.mark.asyncio
async def test_conflicting_detail_preference_waits_for_user_confirmation(monkeypatch):
    old = memory("学生喜欢详细讲解")
    service = service_for(monkeypatch, [old], old)
    new, action = await service.upsert_memory(user_id=old.user_id, course_id=old.course_id,
        memory_type="preference", content="学生喜欢简短讲解", evidence=[str(uuid4())], confidence=0.9)
    assert action == "pending" and new.status == "pending"
    assert new.lifecycle_meta["related_memory_id"] == str(old.id)
    assert old.status == "active" and old.content == "学生喜欢详细讲解"


@pytest.mark.asyncio
async def test_model_foreign_related_id_cannot_overwrite_scoped_memory(monkeypatch):
    service = service_for(monkeypatch, [])
    new, action = await service.upsert_memory(user_id=uuid4(), course_id=uuid4(), memory_type="insight",
        content="需要区分栈和队列", evidence=[str(uuid4())], confidence=0.8,
        related_memory_id=uuid4(), suggested_action="supersede")
    assert action == "pending" and new.lifecycle_meta["review_reason"] == "unknown_related_memory"
