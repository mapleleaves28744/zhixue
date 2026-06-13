from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.learning_analytics import router as learning_analytics_router
from app.core.deps import get_current_user
from app.core.exceptions import register_exception_handlers
from app.db.session import get_db
from app.services.learning_analytics_service import LearningAnalyticsService


class FakeLearningSession:
    def __init__(self, *, session_id: UUID, user_id: UUID, active_seconds: int = 30) -> None:
        self.id = session_id
        self.user_id = user_id
        self.course_id = uuid4()
        self.page = "course-home"
        self.started_at = SimpleNamespace()
        self.last_heartbeat_at = SimpleNamespace()
        self.ended_at = None
        self.active_seconds = active_seconds


class FakeAsyncSession:
    def __init__(self, session: FakeLearningSession | None) -> None:
        self.session = session

    async def get(self, model: object, identity: UUID) -> FakeLearningSession | None:  # noqa: ARG002
        return self.session if self.session and self.session.id == identity else None

    async def commit(self) -> None:
        return None

    async def refresh(self, instance: object) -> None:  # noqa: ARG002
        return None


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(learning_analytics_router, prefix="/api/v1/learning-analytics")
    return app


def _make_client(fake_db: FakeAsyncSession, current_user_id: UUID) -> TestClient:
    app = _build_app()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=current_user_id, role="student")
    app.dependency_overrides[get_db] = lambda: fake_db
    return TestClient(app, raise_server_exceptions=False)


def test_end_session_missing_session_returns_controlled_error() -> None:
    client = _make_client(FakeAsyncSession(None), uuid4())

    response = client.post(f"/api/v1/learning-analytics/sessions/{uuid4()}/end")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == 40401
    assert body["detail"] == "学习会话不存在"


def test_end_session_foreign_session_returns_controlled_error() -> None:
    current_user_id = uuid4()
    foreign_session = FakeLearningSession(session_id=uuid4(), user_id=uuid4())
    client = _make_client(FakeAsyncSession(foreign_session), current_user_id)

    response = client.post(f"/api/v1/learning-analytics/sessions/{foreign_session.id}/end")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == 40401
    assert body["detail"] == "学习会话不存在"


def test_summary_rejects_invalid_period() -> None:
    client = _make_client(FakeAsyncSession(None), uuid4())

    response = client.get("/api/v1/learning-analytics/summary?period=semester")

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == 40002
    assert body["detail"]


def test_build_daily_series_fills_missing_days() -> None:
    now = datetime(2026, 6, 13, 12, 0, tzinfo=UTC)
    series = LearningAnalyticsService._build_daily_series(
        now=now,
        period="week",
        active_map={"2026-06-12": 1200, "2026-06-13": 600},
        activity_map={"2026-06-13": 3},
    )
    assert len(series) == 7
    assert series[0]["date"] == "2026-06-07"
    assert series[-1]["date"] == "2026-06-13"
    assert series[-1]["active_seconds"] == 600
    assert series[-1]["activity_count"] == 3
    assert series[0]["active_seconds"] == 0
