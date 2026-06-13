from datetime import UTC, datetime, timedelta

from app.services.learning_analytics_service import LearningAnalyticsService
from app.services.memory_service import MemoryService
from app.services.strategy_materialization_service import StrategyMaterializationService


def test_memory_key_is_stable_and_normalized() -> None:
    first = MemoryService.build_memory_key("preference", " 喜欢  分步骤讲解 ")
    second = MemoryService.build_memory_key("preference", "喜欢 分步骤讲解")

    assert first == second
    assert first.startswith("preference:")


def test_memory_capacity_is_bounded() -> None:
    assert MemoryService.active_capacity(course_id=None) == 10
    assert MemoryService.active_capacity(course_id="course") == 20


def test_strategy_materialization_only_accepts_executable_types() -> None:
    assert StrategyMaterializationService.normalize_strategy_type("qa_style") == "qa_style"
    assert StrategyMaterializationService.normalize_strategy_type("random_prompt") == "recommendation"


def test_learning_heartbeat_caps_single_increment() -> None:
    now = datetime.now(UTC)

    assert LearningAnalyticsService.calculate_active_delta(now - timedelta(seconds=90), now, active=True) == 60
    assert LearningAnalyticsService.calculate_active_delta(now - timedelta(seconds=20), now, active=True) == 20
    assert LearningAnalyticsService.calculate_active_delta(now - timedelta(seconds=20), now, active=False) == 0

