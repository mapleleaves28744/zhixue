from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.answer_text import extract_final_answer_text
from app.agent_runtime.graph import LearningAgentGraph
from app.agent_runtime.service_tools import build_learning_tool_registry
from app.agent_runtime.supervisor import MiMoSupervisor
from app.agent_runtime.tools import ToolExecutionResult
from app.core.config import settings
from app.llm.provider import get_llm_provider
from app.models.agent_task import AgentTask
from app.models.user import User
from app.repositories.agent_conversation_repository import AgentConversationRepository
from app.repositories.agent_task_repository import AgentTaskRepository
from app.services.agent_queue_service import AgentEventBroker
from app.services.conversation_intent import is_simple_greeting


class AgentTaskCancelled(RuntimeError):
    pass


class AgentRuntimeService:
    def __init__(self, db: AsyncSession, *, broker: AgentEventBroker | None = None) -> None:
        self.db = db
        self.tasks = AgentTaskRepository(db)
        self.conversations = AgentConversationRepository(db)
        self.broker = broker or AgentEventBroker()

    async def execute(self, task_id: UUID, *, approved: bool | None = None) -> dict[str, Any]:
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
            return await self._load_context(task, user)

        async def reviewer(state) -> dict[str, Any]:
            from app.services.agent_service import AgentService

            content = {
                "goal": state.get("goal"),
                "final_answer": state.get("final_answer"),
                "artifacts": state.get("artifacts") or [],
                "citations": state.get("citations") or [],
            }
            result = await AgentService(self.db).run_task(
                task_type="review_content",
                user_id=user.id,
                course_id=task.course_id,
                params={"content": str(content)[:4000]},
            )
            return result.data if result.success else {"pass": False, "issues": [result.message]}

        async def memory_reflector(state) -> dict[str, Any]:
            from app.services.memory_service import MemoryService

            await MemoryService(self.db).reflect(user.id, task.course_id)
            return {}

        async def event_sink(event_type: str, state, payload: dict[str, Any]) -> None:
            await self._record_event(task, registry, event_type, state, payload)

        await self.tasks.update_task(
            task,
            status="running",
            started_at=task.started_at or datetime.now(UTC),
            error_message=None,
        )
        await self.db.commit()

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
                )
                if approved is None:
                    input_payload = task.input_payload or {}
                    result = await graph.run(
                        task_id=task.id,
                        conversation_id=task.conversation_id,
                        user_id=task.user_id,
                        course_id=task.course_id,
                        goal=task.task_goal,
                        thread_id=task.thread_id or str(task.id),
                        messages=[{"role": item.role, "content": item.content} for item in messages],
                        max_iterations=settings.agent_max_iterations,
                        max_tool_calls=settings.agent_max_tool_calls,
                        max_replans=settings.agent_max_replans,
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
            await self._mark_failed(task, exc)
            raise

        await self._finish_task(task, result)
        return result

    async def _load_context(self, task: AgentTask, user: User) -> dict[str, Any]:
        from app.services.memory_service import MemoryService
        from app.services.profile_context_cache import ProfileContextCache
        from app.services.profile_service import ProfileService

        profile = await ProfileContextCache().get_or_load(
            user.id,
            lambda: ProfileService(self.db).get_summary(user.id),
        )
        memories = await MemoryService(self.db).list_memories(user.id, task.course_id)
        return {
            "profile": profile.model_dump(mode="json"),
            "memories": [item.model_dump(mode="json") for item in memories[:20]],
            "course_id": str(task.course_id),
        }

    async def _record_event(
        self,
        task: AgentTask,
        registry,
        event_type: str,
        state: dict[str, Any],
        payload: dict[str, Any],
    ) -> None:
        current = await self._get_task_optional(task.id)
        if current is None:
            return
        if current.status == "cancelled":
            raise AgentTaskCancelled("Agent task was cancelled")
        event = await self.conversations.add_event(
            task_id=task.id,
            conversation_id=task.conversation_id,
            event_type=event_type,
            payload=payload,
        )
        values: dict[str, Any] = {
            "last_event_at": datetime.now(UTC),
            "iteration_count": int(payload.get("iteration_count") or state.get("iteration_count") or 0),
            "tool_call_count": int(state.get("tool_call_count") or 0),
            "replan_count": int(payload.get("replan_count") or state.get("replan_count") or 0),
        }
        if event_type in {"plan_created", "replanned"}:
            values["plan_json"] = {
                **(current.plan_json or {}),
                "plan": payload.get("plan") or [],
                "tool_calls": payload.get("tool_calls") or [],
                "decision_summary": payload.get("summary"),
            }
        if event_type == "waiting_confirmation":
            values.update(status="waiting_confirmation", requires_confirmation=True, risk_level="high")
        elif event_type == "completed":
            values["status"] = "succeeded"
            payload = await self._attach_knowledge_extract(current, payload)
        elif event_type == "failed":
            values["status"] = "failed"
        await self.tasks.update_task(current, **values)

        if event_type == "tool_started":
            tool_call_id = str(payload.get("tool_call_id") or "")
            if tool_call_id and await self.tasks.get_step_by_tool_call(task.id, tool_call_id) is None:
                tool = registry.get(str(payload["tool_name"]))
                await self.tasks.create_dynamic_step(
                    task_id=task.id,
                    step_index=len(await self.tasks.list_steps(task.id)) + 1,
                    agent_name=tool.agent_name,
                    action=tool.name,
                    tool_call_id=tool_call_id,
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
        await self.db.commit()
        await self.broker.publish(task.id, event_type, {**payload, "sequence_no": event.sequence_no})

    async def _attach_knowledge_extract(
        self,
        task: AgentTask,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        answer = str(payload.get("final_answer") or "").strip()
        question = str(task.task_goal or (task.input_payload or {}).get("user_input") or "").strip()
        if not answer or not question:
            return payload
        if is_simple_greeting(question):
            return payload
        try:
            user = await self._get_user(task.user_id)
            from app.services.chat_knowledge_pipeline import (
                extract_knowledge_from_dialogue,
                publish_chat_completed,
                summarize_extract_for_ui,
            )

            extract_result = await extract_knowledge_from_dialogue(
                self.db,
                current_user=user,
                course_id=task.course_id,
                question=question,
                answer=answer,
            )
            summary = summarize_extract_for_ui(extract_result)
            payload = {**payload, "knowledge_extract": summary}
            await publish_chat_completed(
                user_id=task.user_id,
                course_id=task.course_id,
                question=question,
                answer=answer,
                message_id=str(task.id),
                extract_result=extract_result,
                source="agent_runtime_service",
            )
        except Exception:
            pass
        return payload

    async def _mark_failed(self, task: AgentTask, exc: Exception) -> None:
        current = await self._get_task_optional(task.id)
        if current is None or current.status == "cancelled":
            return
        message = str(exc)[:2000] or exc.__class__.__name__
        await self.tasks.update_task(
            current,
            status="failed",
            error_message=message,
            finished_at=datetime.now(UTC),
        )
        event = await self.conversations.add_event(
            task_id=current.id,
            conversation_id=current.conversation_id,
            event_type="failed",
            payload={"status": "failed", "error_message": message},
        )
        await self.db.commit()
        await self.broker.publish(current.id, "failed", {"error_message": message, "sequence_no": event.sequence_no})

    async def _load_tool_result(self, key: str) -> ToolExecutionResult | None:
        task_id, tool_call_id = key.split(":", 1)
        step = await self.tasks.get_step_by_tool_call(UUID(task_id), tool_call_id)
        if step is None or step.status not in {"succeeded", "failed"}:
            return None
        output = dict(step.output_payload or {})
        citations = output.pop("_citations", [])
        return ToolExecutionResult(
            success=step.status == "succeeded",
            output=output,
            evidence=step.evidence,
            artifact_refs=step.artifact_refs,
            citations=citations,
            error_message=step.error_message,
            attempts=step.retry_count + 1,
        )

    async def _save_tool_result(self, key: str, result: ToolExecutionResult) -> None:
        task_id, tool_call_id = key.split(":", 1)
        step = await self.tasks.get_step_by_tool_call(UUID(task_id), tool_call_id)
        if step is None:
            return
        output_payload = dict(result.output or {})
        if result.citations:
            output_payload["_citations"] = result.citations
        await self.tasks.update_step(
            step,
            status="succeeded" if result.success else "failed",
            output_payload=output_payload,
            evidence=result.evidence,
            artifact_refs=result.artifact_refs,
            error_message=result.error_message,
            retry_count=max(0, result.attempts - 1),
            finished_at=datetime.now(UTC),
        )
        await self.db.commit()

    async def _finish_task(self, task: AgentTask, result: dict[str, Any]) -> None:
        current = await self._get_task(task.id)
        if current.status == "cancelled":
            return
        status = result.get("status")
        values: dict[str, Any] = {
            "iteration_count": int(result.get("iteration_count") or 0),
            "tool_call_count": int(result.get("tool_call_count") or 0),
            "replan_count": int(result.get("replan_count") or 0),
            "plan_json": {
                **(current.plan_json or {}),
                "plan": result.get("current_plan") or [],
                "artifact_refs": result.get("artifacts") or [],
                "citations": result.get("citations") or [],
                "decision_summary": result.get("decision_summary"),
                "review_result": result.get("review_result") or {},
            },
        }
        if status == "completed":
            values.update(status="succeeded", finished_at=datetime.now(UTC), error_message=None)
            await self.conversations.add_message(
                conversation=await self._get_conversation(current),
                user_id=current.user_id,
                task_id=current.id,
                role="assistant",
                content=extract_final_answer_text(result.get("final_answer") or ""),
                payload={
                    "artifacts": result.get("artifacts") or [],
                    "citations": result.get("citations") or [],
                    "review_result": result.get("review_result") or {},
                },
            )
        elif status == "waiting_confirmation":
            values.update(status="waiting_confirmation", requires_confirmation=True)
        else:
            values.update(
                status="failed",
                finished_at=datetime.now(UTC),
                error_message=str(result.get("error_message") or "Agent 执行失败")[:2000],
            )
        await self.tasks.update_task(current, **values)
        await self.db.commit()
        if status == "completed":
            from app.services.pet_service import PetService

            await PetService(self.db).safely_create_agent_completion(current)
            artifacts = result.get("artifacts") or []
            if not any(str(item.get("type") or "") == "quiz" for item in artifacts if isinstance(item, dict)):
                try:
                    from app.services.practice_prepush_service import PracticePrepushService

                    await PracticePrepushService(self.db).schedule_from_recent_chat(
                        user_id=current.user_id,
                        course_id=current.course_id,
                    )
                    from app.services.external_resource_prepush_service import ExternalResourcePrepushService

                    await ExternalResourcePrepushService(self.db).schedule_from_recent_chat(
                        user_id=current.user_id,
                        course_id=current.course_id,
                    )
                except Exception:
                    pass

    async def _get_task(self, task_id: UUID) -> AgentTask:
        task = await self._get_task_optional(task_id)
        if task is None:
            raise RuntimeError("Agent task not found")
        return task

    async def _get_task_optional(self, task_id: UUID) -> AgentTask | None:
        task = await self.tasks.get_by_id(task_id)
        if task is None:
            return None
        await self.db.refresh(task)
        return task

    async def _get_user(self, user_id: UUID) -> User:
        user = await self.db.get(User, user_id)
        if user is None:
            raise RuntimeError("Agent task user not found")
        return user

    async def _get_conversation(self, task: AgentTask):
        conversation = await self.conversations.get_for_user(task.conversation_id, task.user_id)
        if conversation is None:
            raise RuntimeError("Agent conversation not found")
        return conversation


def _psycopg_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
