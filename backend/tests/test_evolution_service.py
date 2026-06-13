from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1 import evolution as evolution_api
from app.core.exceptions import BusinessException
from app.models.evolution import EvolutionStrategy
from app.services.evolution_service import EvolutionService


class _FakeExecuteResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


def _build_strategy(*, user_id) -> EvolutionStrategy:
    now = datetime.now(UTC)
    return EvolutionStrategy(
        id=uuid4(),
        user_id=user_id,
        course_id=uuid4(),
        strategy_type="qa_style",
        before_value={"tone": "concise"},
        after_value={"tone": "step_by_step"},
        description="根据近期答疑表现调整讲解风格",
        status="draft",
        risk_level="medium",
        evidence=["近期多次追问链表边界条件"],
        materialized_changes={},
        evaluation_status="pending",
        effect_summary={},
        version_no=1,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_get_strategy_route_passes_current_user_id_to_service() -> None:
    strategy_id = uuid4()
    current_user = SimpleNamespace(id=uuid4())
    request = SimpleNamespace(state=SimpleNamespace(request_id="req_test_evolution_detail"))
    fake_db = object()
    captured: dict[str, object] = {}

    class FakeEvolutionService:
        def __init__(self, db) -> None:
            assert db is fake_db

        async def get_strategy(self, requested_strategy_id, user_id):
            captured["strategy_id"] = requested_strategy_id
            captured["user_id"] = user_id
            return SimpleNamespace(
                model_dump=lambda mode="json": {
                    "id": str(requested_strategy_id),
                    "user_id": str(user_id),
                }
            )

    original_service = evolution_api.EvolutionService
    evolution_api.EvolutionService = FakeEvolutionService
    try:
        response = await evolution_api.get_strategy(
            strategy_id=strategy_id,
            request=request,
            current_user=current_user,
            db=fake_db,
        )
    finally:
        evolution_api.EvolutionService = original_service

    assert captured == {"strategy_id": strategy_id, "user_id": current_user.id}
    assert response["data"]["id"] == str(strategy_id)
    assert response["data"]["user_id"] == str(current_user.id)


@pytest.mark.asyncio
async def test_get_strategy_rejects_other_users_strategy_detail() -> None:
    user_a_id = uuid4()
    user_b_strategy = _build_strategy(user_id=uuid4())

    class FakeSession:
        async def execute(self, statement):
            params = statement.compile().params
            if params.get("id_1") != user_b_strategy.id:
                return _FakeExecuteResult(None)
            if params.get("user_id_1") != user_a_id:
                return _FakeExecuteResult(user_b_strategy)
            return _FakeExecuteResult(None)

    service = EvolutionService(FakeSession())

    with pytest.raises(BusinessException) as exc_info:
        await service.get_strategy(strategy_id=user_b_strategy.id, user_id=user_a_id)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "策略不存在"


def test_evolution_strategy_detail_route_registered() -> None:
    routes = {getattr(route, "path", "") for route in evolution_api.router.routes}

    assert "/strategies/{strategy_id}" in routes
    assert "/strategies/{strategy_id}/reject" in routes


@pytest.mark.asyncio
async def test_reject_strategy_only_allows_draft() -> None:
    user_id = uuid4()
    draft = _build_strategy(user_id=user_id)
    draft.status = "draft"
    active = _build_strategy(user_id=user_id)
    active.status = "active"

    class FakeSession:
        def __init__(self, strategy: EvolutionStrategy) -> None:
            self.strategy = strategy

        async def execute(self, statement):
            return _FakeExecuteResult(self.strategy)

        async def commit(self) -> None:
            return None

        async def refresh(self, obj) -> None:
            return None

    service = EvolutionService(FakeSession(draft))
    result = await service.reject_strategy(draft.id, user_id)
    assert result.status == "rejected"

    service_active = EvolutionService(FakeSession(active))
    with pytest.raises(BusinessException) as exc_info:
        await service_active.reject_strategy(active.id, user_id)
    assert exc_info.value.status_code == 422
