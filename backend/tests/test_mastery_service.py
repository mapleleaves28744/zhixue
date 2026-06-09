from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.services.mastery_service import MasteryService


def test_mastery_learn_rate_increases_score() -> None:
    svc = MasteryService.__new__(MasteryService)
    row = SimpleNamespace(mastery_score=0.2, stability=1.0, last_practiced_at=None, last_asked_at=None)
    row = svc._apply_decay(row, datetime.now(UTC))
    learn = svc.LEARN_RATE * (1.0 - float(row.mastery_score))
    next_score = min(1.0, float(row.mastery_score) + learn)
    assert next_score > row.mastery_score


def test_mastery_wrong_answer_formula_decreases() -> None:
    svc = MasteryService.__new__(MasteryService)
    score = 0.6
    wrong = max(0.0, score - svc.LEARN_RATE * 0.6)
    assert wrong < score


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
