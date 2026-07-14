from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.services.mastery_service import MasteryService


def test_mastery_learn_rate_increases_score() -> None:
    svc = MasteryService.__new__(MasteryService)
    row = SimpleNamespace(mastery_score=0.2, stability=1.0, last_practiced_at=None, last_asked_at=None)
    row = svc._apply_decay(row, datetime.now(UTC))
    next_score = svc._update_score(float(row.mastery_score), outcome=1.0, evidence_count=0)
    assert next_score > row.mastery_score


def test_mastery_wrong_answer_formula_decreases() -> None:
    svc = MasteryService.__new__(MasteryService)
    score = 0.6
    wrong = svc._update_score(score, outcome=0.0, evidence_count=0)
    assert wrong < score


def test_mastery_starts_neutral_and_changes_gradually_with_evidence() -> None:
    svc = MasteryService.__new__(MasteryService)

    assert svc.INITIAL_MASTERY == 0.5
    assert svc._update_score(0.5, outcome=1.0, evidence_count=0) == 0.59
    assert svc._update_score(0.5, outcome=0.0, evidence_count=0) == 0.41
    assert svc._update_score(0.5, outcome=1.0, evidence_count=8) < 0.59


def test_profile_snapshot_marks_no_evidence_as_neutral_pending() -> None:
    svc = MasteryService.__new__(MasteryService)

    snapshot = svc._build_profile_snapshot(course_id=uuid4(), items=[])

    assert snapshot["_algorithm_version"] == "evidence_weighted_v2"
    assert snapshot["_overall"] == 0.5
    assert snapshot["_overall_percent"] == 50.0
    assert snapshot["_evidence_count"] == 0
    assert snapshot["_confidence"] == 0.2
    assert snapshot["_status"] == "pending_validation"


def test_graph_expansion_context_to_dict() -> None:
    from app.rag.graph_expansion import GraphExpansionContext

    ctx = GraphExpansionContext(
        seed_nodes=["栈"],
        expanded_nodes=["队列"],
        relation_paths=[{"from_id": "a", "to_id": "b", "type": "prerequisite"}],
    )
    data = ctx.to_dict()
    assert data["seed_nodes"] == ["栈"]
    assert data["expanded_nodes"] == ["队列"]
    assert data["relation_paths"][0]["type"] == "prerequisite"
