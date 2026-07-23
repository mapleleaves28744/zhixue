# Review package: dc903e0eab8743c2569fbcca2204f47899e13815..HEAD

## Commits
0ffdfc1 fix: atomically claim and observe agent tasks

## Files changed
 backend/app/agent_runtime/graph.py                |  4 ++
 backend/app/repositories/agent_task_repository.py | 14 +++-
 backend/app/services/agent_runtime_service.py     | 25 ++++---
 backend/tests/test_agent_cancellation.py          | 80 +++++++++++++++++++++++
 backend/tests/test_agent_runtime.py               | 58 ++++++++++++++++
 5 files changed, 171 insertions(+), 10 deletions(-)

## Diff
diff --git a/backend/app/agent_runtime/graph.py b/backend/app/agent_runtime/graph.py
index 34cb104..42b9726 100644
--- a/backend/app/agent_runtime/graph.py
+++ b/backend/app/agent_runtime/graph.py
@@ -279,29 +279,33 @@ class LearningAgentGraph:
         )
         await self.event_sink(
             "tool_started",
             state,
             {
                 "tool_call_id": call["id"],
                 "tool_name": name,
                 "arguments": call.get("arguments") or {},
             },
         )
+        tool_started = time.perf_counter()
         result = await self.registry.execute(name, dict(call.get("arguments") or {}), context)
+        duration_ms = int((time.perf_counter() - tool_started) * 1000)
+        result.duration_ms = duration_ms
         await self.event_sink(
             "tool_completed",
             state,
             {
                 "tool_call_id": call["id"],
                 "tool_name": name,
                 "success": result.success,
                 "attempts": result.attempts,
+                "duration_ms": duration_ms,
                 "error_message": result.error_message,
                 "artifact_refs": result.artifact_refs,
             },
         )
         return {
             "status": "executing",
             "pending_tool_calls": pending,
             "tool_call_count": state.get("tool_call_count", 0) + 1,
             "tool_calls": [
                 *(state.get("tool_calls") or []),
diff --git a/backend/app/repositories/agent_task_repository.py b/backend/app/repositories/agent_task_repository.py
index 2848f86..c59f57b 100644
--- a/backend/app/repositories/agent_task_repository.py
+++ b/backend/app/repositories/agent_task_repository.py
@@ -1,18 +1,18 @@
 from __future__ import annotations
 
 from typing import Any
 from uuid import UUID
 
 from datetime import datetime
 
-from sqlalchemy import or_, select
+from sqlalchemy import or_, select, update
 from sqlalchemy.ext.asyncio import AsyncSession
 
 from app.models.agent_task import AgentTask, AgentTaskStep
 from app.schemas.agent_task import AgentTaskPlan
 
 
 class AgentTaskRepository:
     def __init__(self, db: AsyncSession) -> None:
         self.db = db
 
@@ -22,20 +22,32 @@ class AgentTaskRepository:
             .where(
                 AgentTask.status == "queued",
                 AgentTask.started_at.is_(None),
                 AgentTask.runtime_mode == "langgraph",
             )
             .order_by(AgentTask.created_at.asc())
             .limit(limit)
         )
         return list(result.scalars().all())
 
+    async def claim_queued_task(self, task_id: UUID, started_at: datetime) -> bool:
+        result = await self.db.execute(
+            update(AgentTask)
+            .where(
+                AgentTask.id == task_id,
+                AgentTask.status == "queued",
+                AgentTask.runtime_mode == "langgraph",
+            )
+            .values(status="running", started_at=started_at, error_message=None)
+        )
+        return result.rowcount == 1
+
     async def list_stale_running_tasks(self, *, older_than: datetime, limit: int = 20) -> list[AgentTask]:
         result = await self.db.execute(
             select(AgentTask)
             .where(
                 AgentTask.status == "running",
                 AgentTask.runtime_mode == "langgraph",
                 or_(
                     AgentTask.last_event_at.is_(None),
                     AgentTask.last_event_at < older_than,
                 ),
diff --git a/backend/app/services/agent_runtime_service.py b/backend/app/services/agent_runtime_service.py
index 7df0309..6c1625d 100644
--- a/backend/app/services/agent_runtime_service.py
+++ b/backend/app/services/agent_runtime_service.py
@@ -26,41 +26,47 @@ class AgentTaskCancelled(RuntimeError):
 
 
 class AgentRuntimeService:
     def __init__(self, db: AsyncSession, *, broker: AgentEventBroker | None = None) -> None:
         self.db = db
         self.tasks = AgentTaskRepository(db)
         self.conversations = AgentConversationRepository(db)
         self.broker = broker or AgentEventBroker()
 
     async def execute(self, task_id: UUID, *, approved: bool | None = None) -> dict[str, Any]:
+        if not await self.tasks.claim_queued_task(task_id, datetime.now(UTC)):
+            return {"status": "already_claimed"}
+        await self.db.commit()
+
         task = await self._get_task(task_id)
         if task.status == "cancelled":
             return {"status": "cancelled", "final_answer": "任务已由用户取消。"}
         user = await self._get_user(task.user_id)
         messages = await self.conversations.list_messages(task.conversation_id, limit=80)
         provider = get_llm_provider(
             db=self.db,
             user_id=task.user_id,
             course_id=task.course_id,
             allow_mock_fallback=False,
         )
         registry = build_learning_tool_registry(
             self.db,
             user,
             result_loader=self._load_tool_result,
             result_saver=self._save_tool_result,
         )
         supervisor = MiMoSupervisor(provider=provider)
 
         async def context_loader(state) -> dict[str, Any]:
-            return await self._load_context(task, user)
+            context = await self._load_context(task, user)
+            await self.db.commit()
+            return context
 
         async def reviewer(state) -> dict[str, Any]:
             from app.services.agent_service import AgentService
 
             content = {
                 "goal": state.get("goal"),
                 "final_answer": state.get("final_answer"),
                 "artifacts": state.get("artifacts") or [],
                 "citations": state.get("citations") or [],
             }
@@ -74,28 +80,20 @@ class AgentRuntimeService:
 
         async def memory_reflector(state) -> dict[str, Any]:
             from app.services.memory_service import MemoryService
 
             await MemoryService(self.db).reflect(user.id, task.course_id)
             return {}
 
         async def event_sink(event_type: str, state, payload: dict[str, Any]) -> None:
             await self._record_event(task, registry, event_type, state, payload)
 
-        await self.tasks.update_task(
-            task,
-            status="running",
-            started_at=task.started_at or datetime.now(UTC),
-            error_message=None,
-        )
-        await self.db.commit()
-
         try:
             async with AsyncPostgresSaver.from_conn_string(_psycopg_url(settings.database_url)) as checkpointer:
                 graph = LearningAgentGraph(
                     registry=registry,
                     supervisor=supervisor,
                     checkpointer=checkpointer,
                     context_loader=context_loader,
                     reviewer=reviewer,
                     memory_reflector=memory_reflector,
                     event_sink=event_sink,
@@ -116,20 +114,21 @@ class AgentRuntimeService:
                         tool_hints=list(input_payload.get("tool_hints") or []),
                         skip_tools=list(input_payload.get("skip_tools") or []),
                         tool_topics=dict(input_payload.get("tool_topics") or {}),
                         parsed_intents=list(input_payload.get("parsed_intents") or []),
                     )
                 else:
                     result = await graph.resume(thread_id=task.thread_id or str(task.id), approved=approved)
         except AgentTaskCancelled:
             return {"status": "cancelled", "final_answer": "任务已由用户取消。"}
         except Exception as exc:
+            await self.db.rollback()
             await self._mark_failed(task, exc)
             raise
 
         await self._finish_task(task, result)
         return result
 
     async def _load_context(self, task: AgentTask, user: User) -> dict[str, Any]:
         from app.services.memory_service import MemoryService
         from app.services.profile_context_cache import ProfileContextCache
         from app.services.profile_service import ProfileService
@@ -198,20 +197,27 @@ class AgentRuntimeService:
                     iteration_no=int(state.get("iteration_count") or 0),
                     status="running",
                     input_payload=dict(payload.get("arguments") or {}),
                     output_payload={},
                     evidence=[],
                     artifact_refs=[],
                     error_message=None,
                     retry_count=0,
                     decision_summary=state.get("decision_summary"),
                 )
+        elif event_type == "tool_completed":
+            tool_call_id = str(payload.get("tool_call_id") or "")
+            duration_ms = payload.get("duration_ms")
+            if tool_call_id and isinstance(duration_ms, int):
+                step = await self.tasks.get_step_by_tool_call(task.id, tool_call_id)
+                if step is not None:
+                    await self.tasks.update_step(step, duration_ms=duration_ms)
         await self.db.commit()
         await self.broker.publish(task.id, event_type, {**payload, "sequence_no": event.sequence_no})
 
     async def _mark_failed(self, task: AgentTask, exc: Exception) -> None:
         current = await self._get_task_optional(task.id)
         if current is None or current.status == "cancelled":
             return
         message = str(exc)[:2000] or exc.__class__.__name__
         await self.tasks.update_task(
             current,
@@ -258,20 +264,21 @@ class AgentRuntimeService:
         if result.final_answer:
             output_payload["_final_answer"] = result.final_answer
         await self.tasks.update_step(
             step,
             status="succeeded" if result.success else "failed",
             output_payload=output_payload,
             evidence=result.evidence,
             artifact_refs=result.artifact_refs,
             error_message=result.error_message,
             retry_count=max(0, result.attempts - 1),
+            duration_ms=getattr(result, "duration_ms", None),
             finished_at=datetime.now(UTC),
         )
         await self.db.commit()
 
     async def _finish_task(self, task: AgentTask, result: dict[str, Any]) -> None:
         current = await self._get_task(task.id)
         if current.status == "cancelled":
             return
         status = result.get("status")
         values: dict[str, Any] = {
diff --git a/backend/tests/test_agent_cancellation.py b/backend/tests/test_agent_cancellation.py
index 9d0e358..862be8a 100644
--- a/backend/tests/test_agent_cancellation.py
+++ b/backend/tests/test_agent_cancellation.py
@@ -6,29 +6,33 @@ from uuid import UUID, uuid4
 
 import pytest
 
 from app.services.agent_runtime_service import AgentRuntimeService, AgentTaskCancelled
 
 
 class FakeAsyncSession:
     def __init__(self, authoritative_status: dict[UUID, str]) -> None:
         self.authoritative_status = authoritative_status
         self.commit_calls = 0
+        self.rollback_calls = 0
 
     async def refresh(self, instance: object) -> None:
         task_id = getattr(instance, "id", None)
         if task_id in self.authoritative_status:
             setattr(instance, "status", self.authoritative_status[task_id])
 
     async def commit(self) -> None:
         self.commit_calls += 1
 
+    async def rollback(self) -> None:
+        self.rollback_calls += 1
+
     async def get(self, model: object, identity: UUID) -> object | None:  # noqa: ARG002
         return None
 
 
 class FakeTaskRepository:
     def __init__(self, task: SimpleNamespace) -> None:
         self.task = task
         self.update_calls: list[dict[str, object]] = []
 
     async def get_by_id(self, task_id: UUID) -> SimpleNamespace | None:
@@ -43,20 +47,31 @@ class FakeTaskRepository:
     async def get_step_by_tool_call(self, task_id: UUID, tool_call_id: str) -> None:  # noqa: ARG002
         return None
 
     async def list_steps(self, task_id: UUID) -> list[object]:  # noqa: ARG002
         return []
 
     async def create_dynamic_step(self, **kwargs: object) -> object:
         raise AssertionError("cancelled tasks must not create dynamic steps")
 
 
+class ClaimTaskRepository(FakeTaskRepository):
+    def __init__(self, task: SimpleNamespace, *, claim_succeeds: bool) -> None:
+        super().__init__(task)
+        self.claim_succeeds = claim_succeeds
+        self.claim_calls = 0
+
+    async def claim_queued_task(self, task_id: UUID, started_at: object) -> bool:  # noqa: ARG002
+        self.claim_calls += 1
+        return self.claim_succeeds
+
+
 class FakeConversationRepository:
     def __init__(self) -> None:
         self.events: list[dict[str, object]] = []
         self.messages: list[dict[str, object]] = []
 
     async def add_event(
         self,
         *,
         task_id: UUID,
         conversation_id: UUID | None,
@@ -73,20 +88,23 @@ class FakeConversationRepository:
         )
         return SimpleNamespace(sequence_no=len(self.events))
 
     async def add_message(self, **kwargs: object) -> SimpleNamespace:
         self.messages.append(kwargs)
         return SimpleNamespace()
 
     async def get_for_user(self, conversation_id: UUID, user_id: UUID) -> SimpleNamespace:  # noqa: ARG002
         return SimpleNamespace(id=conversation_id)
 
+    async def list_messages(self, conversation_id: UUID, limit: int = 80) -> list[SimpleNamespace]:  # noqa: ARG002
+        return []
+
 
 class FakeBroker:
     def __init__(self) -> None:
         self.published: list[tuple[UUID, str, dict[str, object]]] = []
 
     async def publish(self, task_id: UUID, event_type: str, payload: dict[str, object]) -> None:
         self.published.append((task_id, event_type, payload))
 
 
 def _build_task(*, status: str = "running") -> SimpleNamespace:
@@ -108,20 +126,31 @@ def _build_service(task: SimpleNamespace) -> tuple[AgentRuntimeService, FakeTask
     db = FakeAsyncSession({task.id: "cancelled"})
     tasks = FakeTaskRepository(task)
     conversations = FakeConversationRepository()
     broker = FakeBroker()
     service = AgentRuntimeService(db, broker=broker)
     service.tasks = tasks
     service.conversations = conversations
     return service, tasks, conversations, broker
 
 
+def build_runtime_service_for_claim(
+    claim_succeeds: bool,
+) -> tuple[AgentRuntimeService, SimpleNamespace]:
+    task = _build_task(status="queued")
+    db = FakeAsyncSession({task.id: "queued"})
+    service = AgentRuntimeService(db, broker=FakeBroker())
+    service.tasks = ClaimTaskRepository(task, claim_succeeds=claim_succeeds)
+    service.conversations = FakeConversationRepository()
+    return service, task
+
+
 @pytest.mark.asyncio
 async def test_record_event_does_not_turn_cancelled_task_into_succeeded(
 ) -> None:
     task = _build_task()
     service, tasks, conversations, broker = _build_service(task)
 
     with pytest.raises(AgentTaskCancelled):
         await service._record_event(
             task,
             registry=SimpleNamespace(),
@@ -246,10 +275,61 @@ async def test_finish_task_compensates_when_grounded_postprocess_was_skipped(
 async def test_mark_failed_does_not_turn_cancelled_task_into_failed() -> None:
     task = _build_task()
     service, tasks, conversations, broker = _build_service(task)
 
     await service._mark_failed(task, RuntimeError("late failure"))
 
     assert task.status == "cancelled"
     assert tasks.update_calls == []
     assert conversations.events == []
     assert broker.published == []
+
+
+@pytest.mark.asyncio
+async def test_execute_skips_graph_when_claim_is_owned(
+    monkeypatch: pytest.MonkeyPatch,
+) -> None:
+    service, task = build_runtime_service_for_claim(False)
+    graph_run = AsyncMock()
+    monkeypatch.setattr("app.services.agent_runtime_service.LearningAgentGraph.run", graph_run)
+
+    assert await service.execute(task.id) == {"status": "already_claimed"}
+    graph_run.assert_not_awaited()
+
+
+@pytest.mark.asyncio
+async def test_execute_rolls_back_before_recording_runtime_failure(
+    monkeypatch: pytest.MonkeyPatch,
+) -> None:
+    service, task = build_runtime_service_for_claim(True)
+    marked_failed = AsyncMock()
+
+    async def assert_rollback_then_mark_failed(*args: object) -> None:
+        assert service.db.rollback_calls == 1
+
+    marked_failed.side_effect = assert_rollback_then_mark_failed
+    monkeypatch.setattr(service, "_get_user", AsyncMock(return_value=SimpleNamespace(id=task.user_id)))
+    monkeypatch.setattr(service, "_mark_failed", marked_failed)
+    monkeypatch.setattr(
+        "app.services.agent_runtime_service.AsyncPostgresSaver.from_conn_string",
+        lambda _: _FakeCheckpointerContext(),
+    )
+    graph_run = AsyncMock(side_effect=RuntimeError("graph failed"))
+
+    class FailingGraph:
+        def __init__(self, **kwargs: object) -> None:  # noqa: ARG002
+            self.run = graph_run
+
+    monkeypatch.setattr("app.services.agent_runtime_service.LearningAgentGraph", FailingGraph)
+
+    with pytest.raises(RuntimeError, match="graph failed"):
+        await service.execute(task.id)
+
+    marked_failed.assert_awaited_once()
+
+
+class _FakeCheckpointerContext:
+    async def __aenter__(self) -> object:
+        return object()
+
+    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:  # noqa: ARG002
+        return None
diff --git a/backend/tests/test_agent_runtime.py b/backend/tests/test_agent_runtime.py
index 1eb20c1..752930e 100644
--- a/backend/tests/test_agent_runtime.py
+++ b/backend/tests/test_agent_runtime.py
@@ -323,20 +323,78 @@ async def test_answer_tool_final_answer_bypasses_second_supervisor_call() -> Non
         user_id=uuid4(),
         course_id=uuid4(),
         goal="解释栈",
         thread_id="grounded-pass-through",
     )
 
     assert result["final_answer"] == "栈是 LIFO [S1]。"
     assert supervisor.calls == 1
 
 
+@pytest.mark.asyncio
+async def test_tool_completed_event_has_duration_ms() -> None:
+    class OneToolSupervisor:
+        async def decide(self, state, tool_schemas):
+            if state.get("observations"):
+                return AgentDecision(status="complete", summary="完成", final_answer="栈是后进先出。")
+            return AgentDecision(
+                status="continue",
+                summary="查询课程知识",
+                tool_calls=[
+                    PlannedToolCall(
+                        id="tool-duration-call",
+                        name="search_course_knowledge",
+                        arguments={"query": "栈"},
+                    )
+                ],
+            )
+
+    async def handler(context: ToolContext, arguments: dict[str, object]) -> ToolExecutionResult:
+        return ToolExecutionResult(output={"query": arguments["query"]})
+
+    events: list[tuple[str, dict[str, object]]] = []
+
+    async def event_sink(event_type, state, payload):
+        events.append((event_type, payload))
+
+    registry = ToolRegistry()
+    registry.register(
+        AgentTool(
+            name="search_course_knowledge",
+            description="检索课程知识库",
+            agent_name="KnowledgeAgent",
+            input_schema={
+                "type": "object",
+                "properties": {"query": {"type": "string"}},
+                "required": ["query"],
+            },
+            handler=handler,
+        )
+    )
+    await LearningAgentGraph(
+        registry=registry,
+        supervisor=OneToolSupervisor(),
+        event_sink=event_sink,
+    ).run(
+        task_id=uuid4(),
+        conversation_id=uuid4(),
+        user_id=uuid4(),
+        course_id=uuid4(),
+        goal="解释栈",
+        thread_id="tool-duration",
+    )
+
+    payload = next(payload for kind, payload in events if kind == "tool_completed")
+    assert isinstance(payload["duration_ms"], int)
+    assert payload["duration_ms"] >= 0
+
+
 def test_agent_runtime_no_longer_extracts_dialogue_synchronously() -> None:
     source = (Path(__file__).resolve().parents[1] / "app/services/agent_runtime_service.py").read_text(
         encoding="utf-8"
     )
     assert "extract_knowledge_from_dialogue(" not in source
 
 
 @pytest.mark.asyncio
 async def test_answer_tool_reuses_grounded_pipeline_without_conversation_messages(monkeypatch) -> None:
     from app.schemas.tutor import TutorChatResponse
