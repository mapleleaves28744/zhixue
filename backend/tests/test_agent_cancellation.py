from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from app.services.agent_runtime_service import AgentRuntimeService, AgentTaskCancelled


class FakeAsyncSession:
    def __init__(self, authoritative_status: dict[UUID, str]) -> None:
        self.authoritative_status = authoritative_status
        self.commit_calls = 0
        self.rollback_calls = 0

    async def refresh(self, instance: object) -> None:
        task_id = getattr(instance, "id", None)
        if task_id in self.authoritative_status:
            setattr(instance, "status", self.authoritative_status[task_id])

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1

    async def get(self, model: object, identity: UUID) -> object | None:  # noqa: ARG002
        return None


class FakeTaskRepository:
    def __init__(self, task: SimpleNamespace) -> None:
        self.task = task
        self.update_calls: list[dict[str, object]] = []

    async def get_by_id(self, task_id: UUID) -> SimpleNamespace | None:
        return self.task if self.task.id == task_id else None

    async def update_task(self, task: SimpleNamespace, **values: object) -> SimpleNamespace:
        self.update_calls.append(values)
        for key, value in values.items():
            setattr(task, key, value)
        return task

    async def get_step_by_tool_call(self, task_id: UUID, tool_call_id: str) -> None:  # noqa: ARG002
        return None

    async def list_steps(self, task_id: UUID) -> list[object]:  # noqa: ARG002
        return []

    async def create_dynamic_step(self, **kwargs: object) -> object:
        raise AssertionError("cancelled tasks must not create dynamic steps")


class ClaimTaskRepository(FakeTaskRepository):
    def __init__(self, task: SimpleNamespace, *, claim_succeeds: bool) -> None:
        super().__init__(task)
        self.claim_succeeds = claim_succeeds
        self.claim_calls = 0

    async def claim_queued_task(self, task_id: UUID, started_at: object) -> bool:  # noqa: ARG002
        self.claim_calls += 1
        return self.claim_succeeds


class FakeConversationRepository:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []
        self.messages: list[dict[str, object]] = []

    async def add_event(
        self,
        *,
        task_id: UUID,
        conversation_id: UUID | None,
        event_type: str,
        payload: dict[str, object],
    ) -> SimpleNamespace:
        self.events.append(
            {
                "task_id": task_id,
                "conversation_id": conversation_id,
                "event_type": event_type,
                "payload": payload,
            }
        )
        return SimpleNamespace(sequence_no=len(self.events))

    async def add_message(self, **kwargs: object) -> SimpleNamespace:
        self.messages.append(kwargs)
        return SimpleNamespace()

    async def get_for_user(self, conversation_id: UUID, user_id: UUID) -> SimpleNamespace:  # noqa: ARG002
        return SimpleNamespace(id=conversation_id)

    async def list_messages(self, conversation_id: UUID, limit: int = 80) -> list[SimpleNamespace]:  # noqa: ARG002
        return []


class FakeBroker:
    def __init__(self) -> None:
        self.published: list[tuple[UUID, str, dict[str, object]]] = []

    async def publish(self, task_id: UUID, event_type: str, payload: dict[str, object]) -> None:
        self.published.append((task_id, event_type, payload))


def _build_task(*, status: str = "running") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        course_id=uuid4(),
        conversation_id=uuid4(),
        thread_id="thread-cancel-race",
        task_goal="解释栈",
        plan_json={},
        input_payload={"user_input": "解释栈"},
        started_at=None,
        status=status,
    )


def _build_service(task: SimpleNamespace) -> tuple[AgentRuntimeService, FakeTaskRepository, FakeConversationRepository, FakeBroker]:
    db = FakeAsyncSession({task.id: "cancelled"})
    tasks = FakeTaskRepository(task)
    conversations = FakeConversationRepository()
    broker = FakeBroker()
    service = AgentRuntimeService(db, broker=broker)
    service.tasks = tasks
    service.conversations = conversations
    return service, tasks, conversations, broker


def build_runtime_service_for_claim(
    claim_succeeds: bool,
) -> tuple[AgentRuntimeService, SimpleNamespace]:
    task = _build_task(status="queued")
    db = FakeAsyncSession({task.id: "queued"})
    service = AgentRuntimeService(db, broker=FakeBroker())
    service.tasks = ClaimTaskRepository(task, claim_succeeds=claim_succeeds)
    service.conversations = FakeConversationRepository()
    return service, task


@pytest.mark.asyncio
async def test_record_event_does_not_turn_cancelled_task_into_succeeded(
) -> None:
    task = _build_task()
    service, tasks, conversations, broker = _build_service(task)

    with pytest.raises(AgentTaskCancelled):
        await service._record_event(
            task,
            registry=SimpleNamespace(),
            event_type="completed",
            state={},
            payload={"final_answer": "栈是后进先出。"},
        )

    assert task.status == "cancelled"
    assert tasks.update_calls == []
    assert conversations.events == []
    assert broker.published == []


@pytest.mark.asyncio
async def test_finish_task_does_not_turn_cancelled_task_into_succeeded() -> None:
    task = _build_task()
    service, tasks, conversations, broker = _build_service(task)

    await service._finish_task(
        task,
        {
            "status": "completed",
            "final_answer": "栈是后进先出。",
            "artifacts": [],
            "citations": [],
        },
    )

    assert task.status == "cancelled"
    assert tasks.update_calls == []
    assert conversations.messages == []
    assert broker.published == []


@pytest.mark.asyncio
async def test_finish_task_reuses_grounded_record_without_duplicate_publish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = _build_task(status="running")
    db = FakeAsyncSession({task.id: "running"})
    service = AgentRuntimeService(db, broker=FakeBroker())
    service.tasks = FakeTaskRepository(task)
    conversations = FakeConversationRepository()
    service.conversations = conversations
    publish = AsyncMock()
    monkeypatch.setattr(service, "_publish_chat_completed", publish)

    from app.services.pet_service import PetService

    monkeypatch.setattr(PetService, "safely_create_agent_completion", AsyncMock())
    record_id = uuid4()
    await service._finish_task(
        task,
        {
            "status": "completed",
            "final_answer": "栈是后进先出 [S1]。",
            "artifacts": [],
            "citations": [{"citation_key": "S1"}],
            "observations": [
                {
                    "success": True,
                    "tool_name": "answer_course_question",
                        "output": {
                            "message_id": str(record_id),
                            "postprocess_status": "queued",
                        "grounding_status": "grounded",
                        "grounding_message": "回答已绑定课程依据。",
                        "follow_up_questions": ["能举例吗？"],
                        "related_knowledge_points": [{"name": "栈"}],
                    },
                }
            ],
        },
    )

    publish.assert_not_awaited()
    payload = conversations.messages[0]["payload"]
    assert payload["learning_record_id"] == str(record_id)
    assert payload["grounding_status"] == "grounded"


@pytest.mark.asyncio
async def test_finish_task_compensates_when_grounded_postprocess_was_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = _build_task(status="running")
    db = FakeAsyncSession({task.id: "running"})
    service = AgentRuntimeService(db, broker=FakeBroker())
    service.tasks = FakeTaskRepository(task)
    service.conversations = FakeConversationRepository()
    publish = AsyncMock()
    monkeypatch.setattr(service, "_publish_chat_completed", publish)

    from app.services.pet_service import PetService

    monkeypatch.setattr(PetService, "safely_create_agent_completion", AsyncMock())
    result = {
        "status": "completed",
        "final_answer": "课程依据不足。",
        "artifacts": [],
        "citations": [],
        "observations": [
            {
                "success": True,
                "tool_name": "answer_course_question",
                "output": {
                    "answer": "课程依据不足。",
                    "message_id": None,
                    "postprocess_status": "skipped",
                },
            }
        ],
    }

    await service._finish_task(task, result)

    publish.assert_awaited_once_with(task, result)


@pytest.mark.asyncio
async def test_mark_failed_does_not_turn_cancelled_task_into_failed() -> None:
    task = _build_task()
    service, tasks, conversations, broker = _build_service(task)

    await service._mark_failed(task, RuntimeError("late failure"))

    assert task.status == "cancelled"
    assert tasks.update_calls == []
    assert conversations.events == []
    assert broker.published == []


@pytest.mark.asyncio
async def test_execute_skips_graph_when_claim_is_owned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, task = build_runtime_service_for_claim(False)
    graph_run = AsyncMock()
    monkeypatch.setattr("app.services.agent_runtime_service.LearningAgentGraph.run", graph_run)

    assert await service.execute(task.id) == {"status": "already_claimed"}
    graph_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_rolls_back_before_recording_runtime_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, task = build_runtime_service_for_claim(True)
    marked_failed = AsyncMock()

    async def assert_rollback_then_mark_failed(*args: object) -> None:
        assert service.db.rollback_calls == 1

    marked_failed.side_effect = assert_rollback_then_mark_failed
    monkeypatch.setattr(service, "_get_user", AsyncMock(return_value=SimpleNamespace(id=task.user_id)))
    monkeypatch.setattr(service, "_mark_failed", marked_failed)
    monkeypatch.setattr(
        "app.services.agent_runtime_service.AsyncPostgresSaver.from_conn_string",
        lambda _: _FakeCheckpointerContext(),
    )
    graph_run = AsyncMock(side_effect=RuntimeError("graph failed"))

    class FailingGraph:
        def __init__(self, **kwargs: object) -> None:  # noqa: ARG002
            self.run = graph_run

    monkeypatch.setattr("app.services.agent_runtime_service.LearningAgentGraph", FailingGraph)

    with pytest.raises(RuntimeError, match="graph failed"):
        await service.execute(task.id)

    marked_failed.assert_awaited_once()


class _FakeCheckpointerContext:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:  # noqa: ARG002
        return None
