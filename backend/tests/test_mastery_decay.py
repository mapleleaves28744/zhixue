"""掌握度遗忘曲线衰减测试。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.services.mastery_service import MasteryService


def test_apply_decay_reduces_stale_mastery() -> None:
    svc = MasteryService.__new__(MasteryService)
    row = SimpleNamespace(
        mastery_score=0.8,
        stability=2.0,
        last_practiced_at=datetime.now(UTC) - timedelta(days=7),
        last_asked_at=None,
        evidence_json={},
    )
    svc._apply_decay(row, datetime.now(UTC))
    assert float(row.mastery_score) < 0.8
    assert row.evidence_json.get("decay_days", 0) >= 7


def test_apply_decay_preserves_first_day_and_neutral_floor() -> None:
    svc = MasteryService.__new__(MasteryService)
    row = SimpleNamespace(
        mastery_score=0.5,
        stability=1.0,
        last_practiced_at=datetime.now(UTC) - timedelta(hours=12),
        last_asked_at=None,
        evidence_json={},
    )
    svc._apply_decay(row, datetime.now(UTC))
    assert row.mastery_score == 0.5

    row.last_practiced_at = datetime.now(UTC) - timedelta(days=30)
    svc._apply_decay(row, datetime.now(UTC))
    assert row.mastery_score >= svc.MASTERY_FLOOR
