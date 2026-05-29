"""Phase 16 tests: diagnosis rules and recommendation API surface."""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import BusinessException
from app.main import app
from app.services.diagnosis_service import DiagnosisService
from app.services.recommendation_service import RecommendationService


def test_diagnosis_rules_build_weak_points_and_actions() -> None:
    service = DiagnosisService.__new__(DiagnosisService)
    weak_points = service._build_weak_points(
        [
            {
                "knowledge_id": str(uuid4()),
                "knowledge_name": "栈与队列",
                "mastery_level": 0.4,
                "total_attempts": 5,
                "correct_count": 2,
            },
            {
                "knowledge_id": str(uuid4()),
                "knowledge_name": "图的遍历",
                "mastery_level": 0.9,
                "total_attempts": 5,
                "correct_count": 5,
            },
        ],
        [],
    )

    actions = service._build_recommended_actions(weak_points, [])

    assert weak_points[0]["knowledge_name"] == "栈与队列"
    assert weak_points[0]["severity"] == "high"
    assert actions[0]["action_type"] == "review_and_practice"
    assert "栈与队列" in actions[0]["title"]


def test_diagnosis_fallback_action_uses_course_title() -> None:
    service = DiagnosisService.__new__(DiagnosisService)

    actions = service._build_recommended_actions([], [], course_title="离散数学")

    assert actions[0]["action_type"] == "continue_learning"
    assert actions[0]["title"] == "继续完成一组《离散数学》练习"
    assert "数据结构" not in actions[0]["title"]


def test_diagnosis_error_patterns_use_answer_tags() -> None:
    service = DiagnosisService.__new__(DiagnosisService)
    patterns = service._build_error_patterns(
        [
            SimpleNamespace(error_tags=["概念混淆"], is_correct=False),
            SimpleNamespace(error_tags=["概念混淆", "边界条件错误"], is_correct=False),
        ],
        [],
    )

    assert patterns[0]["pattern"] == "概念混淆"
    assert patterns[0]["count"] == 2


@pytest.mark.asyncio
async def test_recommendation_update_status_rejects_invalid_status() -> None:
    service = RecommendationService.__new__(RecommendationService)

    async def fake_get_owned_recommendation(item_id, user_id):
        return SimpleNamespace(id=item_id, user_id=user_id, status="pending")

    service._get_owned_recommendation = fake_get_owned_recommendation
    current_user = SimpleNamespace(id=uuid4())

    with pytest.raises(BusinessException):
        await service.update_status(
            item_id=uuid4(),
            current_user=current_user,
            status="invalid",
        )


def test_phase16_routes_are_registered() -> None:
    routes = {getattr(route, "path", "") for route in app.routes}

    assert "/api/v1/diagnosis/generate" in routes
    assert "/api/v1/diagnosis/reports/{report_id}" in routes
    assert "/api/v1/diagnosis/mastery" in routes
    assert "/api/v1/recommendations" in routes
    assert "/api/v1/recommendations/refresh" in routes
