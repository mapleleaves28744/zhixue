from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest

from app.core.deps import get_current_user, get_db
from app.core.exceptions import BusinessException
from app.main import app
from app.services.ab_test_service import ABTestService


@pytest.fixture(autouse=True)
def _clear_dependency_overrides() -> None:
    original = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original)


class _FakeScalarResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object:
        return self._value


class _FakeUpdateResult:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class _FakeDbForMetric:
    def __init__(self, assignment_group: str | None) -> None:
        self.assignment_group = assignment_group
        self.execute_calls = 0
        self.flushed = False

    async def get(self, model: object, ident: UUID) -> SimpleNamespace:
        return SimpleNamespace(id=ident, status="running")

    async def execute(self, stmt: object) -> object:
        self.execute_calls += 1
        if self.execute_calls == 1:
            return _FakeScalarResult(self.assignment_group)
        return _FakeUpdateResult(1)

    async def flush(self) -> None:
        self.flushed = True


def _make_user(role: str) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), username=f"{role}_user", role=role)


async def _override_db() -> object:
    yield SimpleNamespace()


@pytest.mark.asyncio
async def test_record_metric_raises_when_assignment_missing() -> None:
    db = _FakeDbForMetric(assignment_group=None)
    service = ABTestService(db)  # type: ignore[arg-type]

    with pytest.raises(BusinessException) as exc:
        await service.record_metric(uuid4(), uuid4(), 0.82)

    assert exc.value.status_code == 404
    assert "尚未分配" in str(exc.value.detail)
    assert db.execute_calls == 1
    assert db.flushed is False


@pytest.mark.asyncio
async def test_record_metric_updates_existing_assignment() -> None:
    db = _FakeDbForMetric(assignment_group="control")
    service = ABTestService(db)  # type: ignore[arg-type]

    await service.record_metric(uuid4(), uuid4(), 0.91)

    assert db.execute_calls == 2
    assert db.flushed is True


@pytest.mark.asyncio
async def test_ab_test_stats_requires_admin_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_test_stats(self: ABTestService, test_id: UUID) -> dict[str, object]:
        return {
            "test_id": str(test_id),
            "name": "AB 实验",
            "status": "running",
            "winner": None,
            "groups": {},
        }

    monkeypatch.setattr(ABTestService, "get_test_stats", fake_get_test_stats)
    async def override_get_current_user() -> SimpleNamespace:
        return _make_user("student")

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = _override_db

    test_id = uuid4()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/ab-tests/{test_id}/stats")

    assert response.status_code == 403
    body = response.json()
    assert body["code"] == 40301
    assert body["detail"] == "需要管理员权限"


@pytest.mark.asyncio
async def test_ab_test_stats_allows_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_test_stats(self: ABTestService, test_id: UUID) -> dict[str, object]:
        return {
            "test_id": str(test_id),
            "name": "AB 实验",
            "status": "running",
            "winner": "treatment",
            "groups": {"control": {"count": 10, "avg_metric": 0.5}},
        }

    monkeypatch.setattr(ABTestService, "get_test_stats", fake_get_test_stats)
    async def override_get_current_user() -> SimpleNamespace:
        return _make_user("admin")

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = _override_db

    test_id = uuid4()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/ab-tests/{test_id}/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["test_id"] == str(test_id)
    assert body["data"]["winner"] == "treatment"
