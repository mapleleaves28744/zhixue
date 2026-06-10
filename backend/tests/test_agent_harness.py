"""Agent / multimodal harness: policy enforcement, requeue, media auth, orphan recovery."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agent_runtime.supervisor import MiMoSupervisor
from app.core.security import create_access_token
from app.llm.schemas import ChatResponse
from app.services.agent_conversation_service import AgentConversationService
from app.services.agent_queue_service import AgentQueueService


class DirectUngroundedAnswerProvider:
    async def chat(self, messages, **kwargs):
        return ChatResponse(
            content='{"status":"complete","summary":"直接回答","final_answer":"这是一段未调用工具的 Markdown。"}'
        )


@pytest.mark.asyncio
async def test_supervisor_blocks_zero_tool_multimodal_complete() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": name,
                "parameters": {"type": "object", "properties": {"topic": {"type": "string"}}},
            },
        }
        for name in ("search_course_knowledge", "generate_educational_image")
    ]
    decision = await MiMoSupervisor(provider=DirectUngroundedAnswerProvider()).decide(
        {
            "goal": "请基于课程资料为 BFS 生成一张教学插图，并给出引用。",
            "messages": [],
            "observations": [],
            "citations": [],
            "tool_call_count": 0,
        },
        tools,
    )

    assert decision.status == "continue"
    assert decision.tool_calls[0].name == "search_course_knowledge"


@pytest.mark.asyncio
async def test_supervisor_routes_bfs_image_goal_to_educational_image_after_search() -> None:
    supervisor = MiMoSupervisor(provider=DirectUngroundedAnswerProvider())
    tools = [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": name,
                "parameters": {"type": "object", "properties": {"topic": {"type": "string"}}},
            },
        }
        for name in ("search_course_knowledge", "generate_educational_image")
    ]
    decision = await supervisor.decide(
        {
            "goal": "帮我生成一张 BFS 的教学插图",
            "messages": [],
            "observations": [
                {
                    "success": True,
                    "tool_name": "search_course_knowledge",
                    "output": {"citations": [{"title": "BFS"}]},
                }
            ],
            "citations": [{"title": "BFS"}],
            "tool_call_count": 1,
        },
        tools,
    )

    assert decision.status == "continue"
    assert decision.tool_calls[0].name == "generate_educational_image"
    assert "BFS" in decision.tool_calls[0].arguments["topic"]


class _FakeQueue:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    async def enqueue(self, task_id, *, approved=None, replace=False):
        self.calls.append((task_id, approved, replace))
        return True


class _FakeBroker:
    async def publish(self, task_id, event_type, payload):
        return None


class _FakeConversations:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    async def add_event(self, **kwargs):
        event = SimpleNamespace(sequence_no=len(self.events) + 1, payload=kwargs.get("payload") or {})
        self.events.append(kwargs)
        return event


class _FakeTasks:
    def __init__(self, task: SimpleNamespace) -> None:
        self.task = task

    async def get_for_user(self, task_id, user_id):
        if self.task.id == task_id and self.task.user_id == user_id:
            return self.task
        return None


class _FakeDb:
    async def commit(self) -> None:
        return None


@pytest.mark.asyncio
async def test_requeue_task_re_enqueues_orphaned_queued_task() -> None:
    task_id = uuid4()
    user_id = uuid4()
    task = SimpleNamespace(
        id=task_id,
        user_id=user_id,
        conversation_id=uuid4(),
        course_id=uuid4(),
        task_goal="demo",
        task_type="dynamic_agent",
        plan_schema_version="1.0",
        plan_json={},
        risk_level="low",
        requires_confirmation=False,
        status="queued",
        started_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    queue = _FakeQueue()
    conversations = _FakeConversations()
    service = AgentConversationService(_FakeDb(), queue=queue, broker=_FakeBroker())  # type: ignore[arg-type]
    service.tasks = _FakeTasks(task)  # type: ignore[assignment]
    service.conversations = conversations  # type: ignore[assignment]

    result = await service.requeue_task(task_id, SimpleNamespace(id=user_id))

    assert result.id == task_id
    assert queue.calls == [(task_id, None, True)]
    assert conversations.events[-1]["event_type"] == "queued"


@pytest.mark.asyncio
async def test_recover_orphaned_tasks_enqueues_each_id() -> None:
    class _Pool:
        async def enqueue_job(self, *args, **kwargs):
            return SimpleNamespace(job_id=kwargs.get("_job_id"))

        async def aclose(self) -> None:
            return None

    async def _fake_pool(*args, **kwargs):
        return _Pool()

    import app.services.agent_queue_service as module

    original = module.create_pool
    module.create_pool = _fake_pool  # type: ignore[assignment]
    try:
        recovered = await AgentQueueService("redis://localhost:6379/0").recover_orphaned_tasks(
            [uuid4(), uuid4()]
        )
    finally:
        module.create_pool = original

    assert recovered == 2


def test_media_file_route_supports_query_token_auth() -> None:
    from app.main import app

    paths = app.openapi()["paths"]
    file_route = paths["/api/v1/media-assets/{asset_id}/file"]["get"]
    param_names = {item["name"] for item in file_route.get("parameters") or []}
    assert "access_token" in param_names


def test_agent_requeue_route_registered() -> None:
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/agent/tasks/{task_id}/requeue" in paths


def test_course_material_exported_from_models_package() -> None:
    from app.models import CourseMaterial

    assert CourseMaterial.__tablename__ == "course_materials"


def test_access_token_can_be_created_for_media_query_auth() -> None:
    user_id = uuid4()
    token, _expires = create_access_token(user_id, "demo", "student")
    assert isinstance(token, str)
    assert len(token) > 20
