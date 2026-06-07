from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.agents.context import AgentContext
from app.agents.intent_router_agent import IntentRouterAgent
from app.agent_graphs.learning_task_graph import LearningTaskGraph, StepExecutionResult
from app.core.exceptions import BusinessException
from app.models.agent_task import AgentTask, AgentTaskStep
from app.schemas.agent_task import (
    AgentTaskPlan,
    AgentTaskPlanStep,
    build_task_plan,
)
from app.services.agent_task_service import AgentTaskService


class _FakeDb:
    pass


@pytest.mark.asyncio
async def test_intent_router_parses_complex_learning_package() -> None:
    agent = IntentRouterAgent(_FakeDb())  # type: ignore[arg-type]
    result = await agent.run(
        AgentContext(
            user_id=uuid4(),
            course_id=uuid4(),
            task_type="route_intent",
            params={
                "user_input": "我最近图和排序不太会，帮我生成一套学习计划、讲解资料、练习题和一个课堂讲解。"
            },
        )
    )

    assert result.success is True
    assert result.data["task_type"] == "personalized_learning_package"
    assert result.data["target_knowledge"] == ["图", "排序"]
    assert result.data["requested_artifacts"] == [
        "learning_path",
        "doc",
        "quiz",
        "html_classroom",
    ]
    assert result.data["risk_level"] == "low"
    assert result.data["requires_confirmation"] is False


@pytest.mark.asyncio
async def test_intent_router_marks_destructive_request_for_confirmation() -> None:
    agent = IntentRouterAgent(_FakeDb())  # type: ignore[arg-type]
    result = await agent.run(
        AgentContext(
            user_id=uuid4(),
            course_id=uuid4(),
            task_type="route_intent",
            params={"user_input": "批量重建知识库并覆盖 Wiki 页面后发布。"},
        )
    )

    assert result.success is True
    assert result.data["risk_level"] == "high"
    assert result.data["requires_confirmation"] is True


def test_agent_task_plan_rejects_unknown_agent_action() -> None:
    with pytest.raises(ValidationError):
        AgentTaskPlan(
            goal="执行任意命令",
            steps=[
                AgentTaskPlanStep(
                    step=1,
                    agent="ShellAgent",
                    action="run_command",
                    expected_output="command_result",
                )
            ],
        )


def test_personalized_learning_package_plan_is_fixed_and_reviewed() -> None:
    plan = build_task_plan(
        {
            "task_type": "personalized_learning_package",
            "goal": "补强图和排序",
            "target_knowledge": ["图", "排序"],
            "requested_artifacts": ["learning_path", "doc", "quiz"],
            "risk_level": "low",
            "requires_confirmation": False,
        }
    )

    assert [step.action for step in plan.steps] == [
        "generate_learning_path",
        "generate_explanation",
        "generate_quiz",
        "review_artifacts",
    ]
    assert plan.steps[-1].agent == "ReviewAgent"


def test_agent_task_service_rejects_run_before_confirmation() -> None:
    service = AgentTaskService.__new__(AgentTaskService)
    task = SimpleNamespace(status="waiting_confirmation")

    with pytest.raises(BusinessException):
        service.ensure_can_run(task)


def test_agent_task_service_allows_only_active_tasks_to_cancel() -> None:
    service = AgentTaskService.__new__(AgentTaskService)

    for status in ("planned", "waiting_confirmation", "running"):
        service.ensure_can_cancel(SimpleNamespace(status=status))

    for status in ("succeeded", "failed", "cancelled"):
        with pytest.raises(BusinessException):
            service.ensure_can_cancel(SimpleNamespace(status=status))


def test_agent_task_models_expose_required_tables_and_fields() -> None:
    assert AgentTask.__tablename__ == "agent_tasks"
    assert AgentTaskStep.__tablename__ == "agent_task_steps"
    assert {
        "user_id",
        "course_id",
        "task_goal",
        "task_type",
        "status",
        "plan_json",
        "risk_level",
        "requires_confirmation",
    }.issubset(AgentTask.__table__.columns.keys())
    assert {
        "task_id",
        "step_index",
        "agent_name",
        "action",
        "status",
        "artifact_refs",
        "evidence",
    }.issubset(AgentTaskStep.__table__.columns.keys())


class _FakeTaskRepository:
    def __init__(self, steps: list[SimpleNamespace]) -> None:
        self.steps = steps

    async def list_steps(self, task_id):
        return self.steps

    async def update_task(self, task, **values):
        for key, value in values.items():
            setattr(task, key, value)
        return task

    async def update_step(self, step, **values):
        for key, value in values.items():
            setattr(step, key, value)
        return step

    async def skip_pending_steps(self, task_id, error_message):
        for step in self.steps:
            if step.status == "pending":
                step.status = "skipped"
                step.error_message = error_message


class _FakeCommitDb:
    async def commit(self) -> None:
        return None


def _task_with_steps(count: int = 3):
    task = SimpleNamespace(
        id=uuid4(),
        status="planned",
        plan_json={},
        task_goal="补强图和排序",
        task_type="personalized_learning_package",
        course_id=uuid4(),
        user_id=uuid4(),
        started_at=None,
        finished_at=None,
        error_message=None,
    )
    steps = [
        SimpleNamespace(
            id=uuid4(),
            task_id=task.id,
            step_index=index,
            agent_name=f"Agent{index}",
            action=f"action_{index}",
            status="pending",
            input_payload={},
            output_payload={},
            artifact_refs=[],
            evidence=[],
            error_message=None,
            started_at=None,
            finished_at=None,
            duration_ms=None,
            related_agent_run_id=None,
        )
        for index in range(1, count + 1)
    ]
    return task, steps


@pytest.mark.asyncio
async def test_learning_task_graph_completes_steps_and_collects_artifacts() -> None:
    task, steps = _task_with_steps()
    repo = _FakeTaskRepository(steps)

    async def execute_step(step, task, current_user, artifacts):
        return StepExecutionResult(
            output={"step": step.step_index},
            evidence=[f"step-{step.step_index}-ok"],
            artifact_refs=[{"type": "resource", "id": str(step.id)}],
        )

    graph = LearningTaskGraph(
        _FakeCommitDb(),  # type: ignore[arg-type]
        repository=repo,  # type: ignore[arg-type]
        step_executor=execute_step,
    )
    await graph.run(task=task, current_user=SimpleNamespace(id=task.user_id))

    assert task.status == "succeeded"
    assert all(step.status == "succeeded" for step in steps)
    assert len(task.plan_json["artifact_refs"]) == 3


@pytest.mark.asyncio
async def test_learning_task_graph_preserves_success_and_skips_remaining_after_failure() -> None:
    task, steps = _task_with_steps()
    repo = _FakeTaskRepository(steps)

    async def execute_step(step, task, current_user, artifacts):
        if step.step_index == 2:
            raise RuntimeError("resource generation failed")
        return StepExecutionResult(output={"ok": True}, artifact_refs=[{"type": "path"}])

    graph = LearningTaskGraph(
        _FakeCommitDb(),  # type: ignore[arg-type]
        repository=repo,  # type: ignore[arg-type]
        step_executor=execute_step,
    )
    await graph.run(task=task, current_user=SimpleNamespace(id=task.user_id))

    assert task.status == "failed"
    assert [step.status for step in steps] == ["succeeded", "failed", "skipped"]
    assert task.plan_json["artifact_refs"] == [{"type": "path"}]


@pytest.mark.asyncio
async def test_learning_task_graph_stops_between_steps_when_task_is_cancelled() -> None:
    task, steps = _task_with_steps()
    repo = _FakeTaskRepository(steps)

    async def execute_step(step, task, current_user, artifacts):
        if step.step_index == 1:
            task.status = "cancelled"
        return StepExecutionResult(output={"ok": True}, artifact_refs=[{"type": "path"}])

    graph = LearningTaskGraph(
        _FakeCommitDb(),  # type: ignore[arg-type]
        repository=repo,  # type: ignore[arg-type]
        step_executor=execute_step,
    )
    await graph.run(task=task, current_user=SimpleNamespace(id=task.user_id))

    assert task.status == "cancelled"
    assert [step.status for step in steps] == ["succeeded", "skipped", "skipped"]


class _OwnedTaskRepository:
    def __init__(self, owner_id) -> None:
        self.owner_id = owner_id
        self.seen_user_id = None

    async def get_for_user(self, task_id, user_id):
        self.seen_user_id = user_id
        if user_id != self.owner_id:
            return None
        return SimpleNamespace(id=task_id, user_id=user_id)


@pytest.mark.asyncio
async def test_agent_task_service_hides_other_users_tasks() -> None:
    owner_id = uuid4()
    repository = _OwnedTaskRepository(owner_id)
    service = AgentTaskService.__new__(AgentTaskService)
    service.tasks = repository

    with pytest.raises(BusinessException) as exc:
        await service._get_owned_task(uuid4(), uuid4())

    assert exc.value.status_code == 404
    assert repository.seen_user_id != owner_id


def test_agent_task_api_routes_are_registered() -> None:
    from app.main import app

    paths = app.openapi()["paths"]
    assert {
        "/api/v1/agent-tasks/create",
        "/api/v1/agent-tasks/{task_id}",
        "/api/v1/agent-tasks/{task_id}/steps",
        "/api/v1/agent-tasks/{task_id}/confirm",
        "/api/v1/agent-tasks/{task_id}/run",
        "/api/v1/agent-tasks/{task_id}/cancel",
    }.issubset(paths)
