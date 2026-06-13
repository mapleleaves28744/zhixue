from __future__ import annotations

from datetime import time
from uuid import uuid4

import pytest

from app.api.v1.router import router
from app.models.pet import PetNotification, PetPreference
from app.schemas.pet import PetPreferenceUpdate
from app.services.pet_service import PetService


def test_pet_models_expose_notification_and_preference_tables() -> None:
    assert PetNotification.__tablename__ == "pet_notifications"
    assert PetPreference.__tablename__ == "pet_preferences"
    assert {"user_id", "dedupe_key", "is_read", "action_url"} <= set(PetNotification.__table__.columns.keys())
    assert {"study_reminders_enabled", "interval_hours", "quiet_start", "quiet_end"} <= set(
        PetPreference.__table__.columns.keys()
    )


def test_pet_routes_are_registered() -> None:
    routes = {route.path for route in router.routes}
    assert "/student/pet/feed" in routes
    assert "/student/pet/notifications/{notification_id}/read" in routes
    assert "/student/pet/notifications/read-all" in routes
    assert "/student/pet/preferences" in routes


def test_pet_preferences_only_allow_supported_intervals() -> None:
    assert PetPreferenceUpdate(interval_hours=2).interval_hours == 2
    with pytest.raises(ValueError):
        PetPreferenceUpdate(interval_hours=3)


def test_quiet_hours_support_overnight_ranges() -> None:
    assert PetService.is_quiet_time(time(23, 0), time(22, 0), time(8, 0)) is True
    assert PetService.is_quiet_time(time(7, 30), time(22, 0), time(8, 0)) is True
    assert PetService.is_quiet_time(time(12, 0), time(22, 0), time(8, 0)) is False


def test_agent_notification_action_restores_original_conversation() -> None:
    course_id = uuid4()
    conversation_id = uuid4()
    task_id = uuid4()
    assert PetService.agent_action_url(course_id, conversation_id, task_id) == (
        f"/assistant?course_id={course_id}&conversation_id={conversation_id}&task_id={task_id}"
    )


@pytest.mark.asyncio
async def test_optional_pet_notification_failure_does_not_escape() -> None:
    class FakeDb:
        rolled_back = False

        async def rollback(self):
            self.rolled_back = True

    db = FakeDb()
    service = PetService(db)  # type: ignore[arg-type]

    async def fail(_task):
        raise RuntimeError("notification storage unavailable")

    service.create_agent_completion = fail  # type: ignore[method-assign]
    await service.safely_create_agent_completion(type("Task", (), {"id": uuid4()})())

    assert db.rolled_back is True
