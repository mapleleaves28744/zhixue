from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.exceptions import BusinessException
from app.main import app


def test_learning_event_batch_schema_accepts_frontend_events() -> None:
    from app.schemas.learning_record import LearningEventBatchRequest

    course_id = uuid4()
    payload = LearningEventBatchRequest(
        events=[
            {
                "course_id": course_id,
                "event_type": "wiki_read",
                "event_payload": {"page_id": str(uuid4())},
            },
            {
                "course_id": course_id,
                "event_type": "quiz_complete",
                "event_source": "stitch_frontend",
                "event_payload": {"score": 80},
            },
        ]
    )

    assert len(payload.events) == 2
    assert payload.events[0].event_source == "frontend"
    assert payload.events[1].event_source == "stitch_frontend"


def test_learning_record_event_type_validator_rejects_unknown_type() -> None:
    from app.api.v1.learning_records import ensure_learning_event_type

    with pytest.raises(BusinessException) as exc:
        ensure_learning_event_type("unknown_event")
    assert "不支持的学习行为类型" in exc.value.detail


def test_learning_record_batch_api_route_registered() -> None:
    paths = app.openapi()["paths"]

    assert "/api/v1/learning-records/events/batch" in paths
