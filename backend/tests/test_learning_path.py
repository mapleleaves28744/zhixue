"""Phase 12 tests: learning path schemas, service, and PlannerAgent."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agents.context import AgentContext, AgentResult
from app.core.exceptions import BusinessException
from app.schemas.learning_path import (
    LearningPathGenerateRequest,
    LearningPathItemRead,
    LearningPathItemUpdate,
    LearningPathRead,
)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestLearningPathSchemas:
    def test_generate_request_defaults(self) -> None:
        req = LearningPathGenerateRequest(course_id=uuid4())
        assert req.goal == "补强当前薄弱知识点"
        assert req.target_knowledge_ids == []
        assert req.path_type == "weakness_repair"

    def test_generate_request_custom_values(self) -> None:
        cid = uuid4()
        kid = uuid4()
        req = LearningPathGenerateRequest(
            course_id=cid,
            goal="掌握图论",
            target_knowledge_ids=[kid],
            path_type="custom",
        )
        assert req.course_id == cid
        assert req.goal == "掌握图论"
        assert kid in req.target_knowledge_ids

    def test_generate_request_empty_goal_rejected(self) -> None:
        with pytest.raises(Exception):
            LearningPathGenerateRequest(course_id=uuid4(), goal="")

    def test_item_update_accepts_valid_statuses(self) -> None:
        for status in ("pending", "doing", "completed", "skipped"):
            item = LearningPathItemUpdate(status=status)
            assert item.status == status

    def test_item_update_rejects_invalid_status(self) -> None:
        with pytest.raises(Exception):
            LearningPathItemUpdate(status="invalid")

    def test_item_read_from_attributes(self) -> None:
        now = datetime.now(UTC)
        obj = SimpleNamespace(
            id=uuid4(),
            path_id=uuid4(),
            knowledge_id=uuid4(),
            wiki_page_id=None,
            title="学习：栈",
            item_type="learn",
            order_index=1,
            status="pending",
            reason="测试理由",
            estimated_minutes=30,
            completed_at=None,
            created_at=now,
        )
        read = LearningPathItemRead.model_validate(obj)
        assert read.title == "学习：栈"
        assert read.status == "pending"

    def test_path_read_includes_items(self) -> None:
        now = datetime.now(UTC)
        item = SimpleNamespace(
            id=uuid4(),
            path_id=uuid4(),
            knowledge_id=None,
            wiki_page_id=None,
            title="节点1",
            item_type="review",
            order_index=1,
            status="completed",
            reason=None,
            estimated_minutes=25,
            completed_at=now,
            created_at=now,
        )
        path = SimpleNamespace(
            id=uuid4(),
            user_id=uuid4(),
            course_id=uuid4(),
            title="测试路径",
            goal="测试目标",
            reason="测试理由",
            status="active",
            progress=Decimal("50.00"),
            strategy_version_id=None,
            created_at=now,
            updated_at=now,
            items=[item],
        )
        read = LearningPathRead.model_validate(path)
        assert len(read.items) == 1
        assert read.items[0].title == "节点1"
        assert read.progress == 50.0


# ---------------------------------------------------------------------------
# PlannerAgent rule-based planning
# ---------------------------------------------------------------------------

class TestPlannerAgentRules:
    def test_build_rule_items_selects_weak_points_first(self) -> None:
        from app.agents.planner_agent import PlannerAgent

        agent = PlannerAgent.__new__(PlannerAgent)
        knowledge_points = [
            {"id": "kp-1", "name": "栈", "sort_order": 1, "difficulty": "easy"},
            {"id": "kp-2", "name": "队列", "sort_order": 2, "difficulty": "easy"},
            {"id": "kp-3", "name": "二叉树", "sort_order": 3, "difficulty": "hard"},
            {"id": "kp-4", "name": "图", "sort_order": 4, "difficulty": "hard"},
        ]
        weak_points = [{"name": "图"}]
        mastery_snapshot = {"kp-1": 0.9, "kp-2": 0.85, "kp-3": 0.5, "kp-4": 0.2}

        items = agent._build_rule_items(
            knowledge_points=knowledge_points,
            weak_points=weak_points,
            mastery_snapshot=mastery_snapshot,
            target_knowledge_ids=set(),
            learning_goal="掌握数据结构",
        )

        assert len(items) <= 5
        names = [it["title"] for it in items]
        assert any("图" in n for n in names)

    def test_build_rule_items_respects_target_ids(self) -> None:
        from app.agents.planner_agent import PlannerAgent

        agent = PlannerAgent.__new__(PlannerAgent)
        knowledge_points = [
            {"id": "kp-1", "name": "栈", "sort_order": 1},
            {"id": "kp-2", "name": "队列", "sort_order": 2},
        ]

        items = agent._build_rule_items(
            knowledge_points=knowledge_points,
            weak_points=[],
            mastery_snapshot={},
            target_knowledge_ids={"kp-2"},
            learning_goal="学习队列",
        )

        assert items
        assert items[0]["knowledge_id"] == "kp-2"

    def test_build_rule_items_empty_input(self) -> None:
        from app.agents.planner_agent import PlannerAgent

        agent = PlannerAgent.__new__(PlannerAgent)
        items = agent._build_rule_items(
            knowledge_points=[],
            weak_points=[],
            mastery_snapshot={},
            target_knowledge_ids=set(),
            learning_goal="空课程",
        )
        assert items == []


# ---------------------------------------------------------------------------
# PlannerAgent run (with mocked LLM and DB)
# ---------------------------------------------------------------------------

class FakePromptService:
    async def render_prompt(self, **kwargs):
        return SimpleNamespace(content="请为学生生成学习计划", prompt_version_id=None)


class FakeLLMResponse:
    content = "学习计划理由：建议先复习基础再深入"
    model = "mock"
    total_tokens = 100


class FakeLLM:
    async def chat(self, messages, **kwargs):
        return FakeLLMResponse()


class FakeDBForAgent:
    """Minimal DB mock that doesn't crash agent init."""
    pass


def test_planner_agent_run_with_mock_llm() -> None:
    asyncio.run(_test_planner_agent_run_with_mock_llm())


async def _test_planner_agent_run_with_mock_llm() -> None:
    from unittest.mock import patch

    from app.agents.planner_agent import PlannerAgent

    agent = PlannerAgent(db=FakeDBForAgent())  # type: ignore[arg-type]
    context = AgentContext(
        user_id=uuid4(),
        course_id=uuid4(),
        task_type="plan_learning",
        params={
            "learning_goal": "掌握栈与队列",
            "knowledge_points": [
                {"id": "kp-1", "name": "栈", "sort_order": 1},
                {"id": "kp-2", "name": "队列", "sort_order": 2},
            ],
            "weak_points": [],
            "mastery_snapshot": {},
            "target_knowledge_ids": [],
        },
    )

    with (
        patch("app.agents.planner_agent.PromptService", return_value=FakePromptService()),
        patch("app.agents.planner_agent.get_llm_provider", return_value=FakeLLM()),
    ):
        result = await agent.run(context)

    assert result.success is True
    assert "items" in result.data
    assert len(result.data["items"]) > 0
    assert "reason" in result.data


def test_planner_agent_missing_goal_returns_error() -> None:
    asyncio.run(_test_planner_agent_missing_goal_returns_error())


async def _test_planner_agent_missing_goal_returns_error() -> None:
    from app.agents.planner_agent import PlannerAgent

    agent = PlannerAgent(db=FakeDBForAgent())  # type: ignore[arg-type]
    context = AgentContext(
        user_id=uuid4(),
        course_id=uuid4(),
        task_type="plan_learning",
        params={},
    )
    result = await agent.run(context)
    assert result.success is False
    assert "learning_goal" in result.message


# ---------------------------------------------------------------------------
# LearningPathService helper methods
# ---------------------------------------------------------------------------

class TestLearningPathServiceHelpers:
    def test_mastery_for_normalizes_percentage(self) -> None:
        from app.services.learning_path_service import LearningPathService

        svc = LearningPathService.__new__(LearningPathService)
        point = SimpleNamespace(id=uuid4(), name="栈")
        snapshot = {str(point.id): 0.75}
        assert svc._mastery_for(point, snapshot) == 75

    def test_mastery_for_handles_full_percentage(self) -> None:
        from app.services.learning_path_service import LearningPathService

        svc = LearningPathService.__new__(LearningPathService)
        point = SimpleNamespace(id=uuid4(), name="栈")
        snapshot = {"栈": 85}
        assert svc._mastery_for(point, snapshot) == 85

    def test_mastery_for_defaults_to_60(self) -> None:
        from app.services.learning_path_service import LearningPathService

        svc = LearningPathService.__new__(LearningPathService)
        point = SimpleNamespace(id=uuid4(), name="未知")
        assert svc._mastery_for(point, {}) == 60

    def test_make_title_weakness_repair(self) -> None:
        from app.services.learning_path_service import LearningPathService

        svc = LearningPathService.__new__(LearningPathService)
        title = svc._make_title("补强图论基础", "weakness_repair")
        assert "补弱路径" in title

    def test_make_title_normal(self) -> None:
        from app.services.learning_path_service import LearningPathService

        svc = LearningPathService.__new__(LearningPathService)
        title = svc._make_title("学习树结构", "normal")
        assert "学习路径" in title

    def test_item_type_for_index_cycles(self) -> None:
        from app.services.learning_path_service import LearningPathService

        svc = LearningPathService.__new__(LearningPathService)
        assert svc._item_type_for_index(1) == "review"
        assert svc._item_type_for_index(2) == "learn"
        assert svc._item_type_for_index(3) == "practice"
        assert svc._item_type_for_index(4) == "summary"
        assert svc._item_type_for_index(5) == "summary"  # clamped

    def test_rule_plan_items_generates_from_knowledge(self) -> None:
        from app.services.learning_path_service import LearningPathService

        svc = LearningPathService.__new__(LearningPathService)
        points = [
            SimpleNamespace(id=uuid4(), name="栈", sort_order=1, difficulty="easy", importance="high"),
            SimpleNamespace(id=uuid4(), name="队列", sort_order=2, difficulty="easy", importance="high"),
            SimpleNamespace(id=uuid4(), name="二叉树", sort_order=3, difficulty="hard", importance="high"),
        ]
        items = svc._rule_plan_items(
            goal="掌握数据结构",
            target_knowledge_ids=[],
            weak_points=[],
            mastery_snapshot={},
            knowledge_points=points,
        )
        assert len(items) == 3
        for item in items:
            assert "knowledge_id" in item
            assert "title" in item
            assert "reason" in item
