from __future__ import annotations

from datetime import UTC, datetime
from dataclasses import replace
from typing import Any
from uuid import UUID

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.answer_text import extract_final_answer_text
from app.agent_runtime.intent_contract import subtask_progress
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
from app.services.conversation_context_service import ConversationContext, ConversationContextService


class AgentTaskCancelled(RuntimeError):
    pass


class AgentRuntimeService:
    def __init__(self, db: AsyncSession, *, broker: AgentEventBroker | None = None) -> None:
        self.db = db
        self.tasks = AgentTaskRepository(db)
        self.conversations = AgentConversationRepository(db)
        self.broker = broker or AgentEventBroker()

    async def execute(self, task_id: UUID, *, approved: bool | None = None) -> dict[str, Any]:
        if not await self.tasks.claim_queued_task(task_id, datetime.now(UTC)):
            return {"status": "already_claimed"}
        await self.db.commit()

        task: AgentTask | None = None
        try:
            task = await self._get_task(task_id)
            if task.status == "cancelled":
                await self.db.rollback()
                return {"status": "cancelled", "final_answer": "任务已由用户取消。"}
            intent_frame = dict((task.input_payload or {}).get("intent_frame_v1") or {})
            # A new conversation with no candidate antecedent can ask directly without a model.
            if intent_frame.get("mode") == "clarify" and not (task.input_payload or {}).get("needs_context_disambiguation"):
                result = {"status": "completed", "final_answer": str(intent_frame.get("clarification_question") or "请补充要学习的知识点。"),
                          "decision_summary": "等待学生补充学习主题。"}
                await self._finish_task(task.id, result)
                await self._publish_direct_completion(task.id, result)
                return result
            user = await self._get_user(task.user_id)
            task_message = await self.conversations.get_task_user_message(task.conversation_id, task.id)
            history_context = (
                await ConversationContextService(self.db).load(
                    conversation_id=task.conversation_id,
                    user_id=user.id,
                    course_id=task.course_id,
                    before_sequence=task_message.sequence_no,
                ) if task_message is not None else ConversationContext()
            )
            if approved is None and (
                ConversationContext.requested_web_ordinal(task.task_goal) is not None
                or ConversationContext.requested_quiz_option(task.task_goal) is not None
                or ConversationContext.requested_material_reference(task.task_goal)
                or ConversationContext.requested_resource_revision(task.task_goal)
            ):
                from app.core.exceptions import BusinessException
                from app.schemas.tutor import TutorChatRequest
                from app.services.course_service import CourseService
                from app.services.tutor_service import TutorService

                course = await CourseService(self.db).get_readable_course(task.course_id, user)
                revision_review: dict[str, Any] = {}
                if ConversationContext.requested_resource_revision(task.task_goal):
                    from app.services.resource_service import ResourceService

                    refs = history_context.resource_references
                    if len(refs) != 1:
                        answer = (
                            "当前会话没有唯一可修订的学习资源。请先生成资源，或明确指出要修订的资源标题。"
                            if not refs else "刚才生成了多个资源。请指出要修订的资源标题。"
                        )
                        citations, provider_name, artifacts = [], "rule", []
                    else:
                        try:
                            target_resource_id = UUID(refs[0]["id"])
                            revision, revision_review = await ResourceService(self.db).revise_resource_from_conversation(
                                resource_id=target_resource_id, course_id=task.course_id,
                                requirement=task.task_goal, current_user=user,
                            )
                            answer = f"已修订「{revision.title}」，新版本为 v{revision.revision_no}；原版本已保留。"
                            citations = list(revision.citations or [])
                            provider_name = revision.model_name or "llm"
                            artifacts = [{
                                "type": "resource", "id": str(revision.id),
                                "resource_id": str(revision.id), "title": revision.title,
                                "resource_type": revision.resource_type,
                                "previous_resource_id": str(revision.previous_resource_id),
                                "revision_no": revision.revision_no,
                            }]
                        except (BusinessException, KeyError, ValueError) as exc:
                            answer = exc.detail if isinstance(exc, BusinessException) else "上一条消息中的资源引用无效，请重新指定资源。"
                            citations, provider_name, artifacts = [], "rule", []
                else:
                    tutor = TutorService(self.db)
                    answer_method = (
                        tutor._answer_quiz_option
                        if ConversationContext.requested_quiz_option(task.task_goal) is not None
                        else tutor._answer_material_reference
                        if ConversationContext.requested_material_reference(task.task_goal)
                        else tutor._answer_web_reference
                    )
                    answer, citations, provider_name = await answer_method(
                        context=history_context,
                        payload=TutorChatRequest(course_id=task.course_id, question=task.task_goal),
                        current_user=user, course=course,
                    )
                    artifacts = []
                result = {
                    "status": "completed", "final_answer": answer,
                    "citations": citations, "provider": provider_name, "artifacts": artifacts,
                    "review_result": revision_review,
                    "decision_summary": "已按会话中的资料、题目或网页引用定位对象。",
                    "direct_reference": True,
                }
                await self._finish_task(task.id, result)
                await self._publish_direct_completion(task.id, result)
                return result
            prompt_context = replace(
                history_context, history=history_context.history[-8:],
                summary="", older_user_requests=(),
            )
            messages = [
                {"role": message.role, "content": message.content}
                for message in prompt_context.messages_for(task.task_goal)
            ]
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
            if approved is None and task_message is not None:
                from app.services.intent_understanding_service import IntentUnderstandingService

                await self.db.commit()
                resolved = await IntentUnderstandingService(self.db).resolve(
                    goal=task.task_goal, frame=intent_frame, context=history_context,
                    provider=provider, tools=registry.tool_schemas(),
                )
                if resolved != intent_frame:
                    task.input_payload = {
                        **(task.input_payload or {}), "intent_frame_v1": resolved,
                        "resolved_goal": resolved.get("resolved_goal") or task.task_goal,
                        "parsed_intents": [{"segment": item["segment"], "topic": item["topic"], "tools": item["tools"]}
                                           for item in resolved["tasks"]],
                        "tool_topics": {name: item["topic"] for item in resolved["tasks"] for name in item["tools"]},
                    }
                    event = await self.conversations.add_event(
                        task_id=task.id, conversation_id=task.conversation_id,
                        event_type="intent_resolved", payload={"parser": resolved.get("parser"), "mode": resolved["mode"], "tasks": resolved["tasks"]},
                    )
                    if resolved["mode"] == "clarify":
                        conversation = await self.conversations.get_for_user_locked(task.conversation_id, user.id)
                        if conversation and conversation.next_message_sequence == task_message.sequence_no:
                            conversation.extra_meta = {**(conversation.extra_meta or {}), "intent_draft_v1": {
                                "kind": "semantic", "goal": task.task_goal,
                                "request_message_id": str(task_message.id), "revision": resolved["revision"],
                            }}
                    await self.db.commit()
                    await self.broker.publish(task.id, "intent_resolved", {**event.payload, "sequence_no": event.sequence_no})
                    if resolved["mode"] == "clarify":
                        result = {"status": "completed", "final_answer": resolved["clarification_question"],
                                  "decision_summary": "需要补充关键要求。"}
                        await self._finish_task(task.id, result)
                        await self._publish_direct_completion(task.id, result)
                        return result
            final_frame = dict((task.input_payload or {}).get("intent_frame_v1") or {})
            if final_frame.get("mode") == "clarify":
                result = {"status": "completed", "final_answer": str(final_frame.get("clarification_question") or "请补充要学习的知识点。"),
                          "decision_summary": "等待学生补充学习主题。"}
                await self._finish_task(task.id, result)
                await self._publish_direct_completion(task.id, result)
                return result
            supervisor = MiMoSupervisor(provider=provider)

            async def context_loader(state) -> dict[str, Any]:
                context = await self._load_context(task, user, history_context=history_context)
                await self.db.commit()
                return context

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
                from app.services.memory_reflection_service import MemoryReflectionService

                await MemoryReflectionService(self.db).discover_missing(
                    user_id=user.id, course_id=task.course_id,
                )
                return {}

            terminal_events: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

            async def event_sink(event_type: str, state, payload: dict[str, Any]) -> None:
                if event_type in {"completed", "failed"}:
                    terminal_events.append((event_type, dict(state), dict(payload)))
                    return
                await self._record_event(task_id, registry, event_type, state, payload)

            await self.db.commit()
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
                        goal=str(input_payload.get("resolved_goal") or task.task_goal),
                        thread_id=task.thread_id or str(task.id),
                        messages=messages,
                        max_iterations=settings.agent_max_iterations,
                        max_tool_calls=settings.agent_max_tool_calls,
                        max_replans=settings.agent_max_replans,
                        tool_hints=list(input_payload.get("tool_hints") or []),
                        skip_tools=list(input_payload.get("skip_tools") or []),
                        tool_topics=dict(input_payload.get("tool_topics") or {}),
                        parsed_intents=list(input_payload.get("parsed_intents") or []),
                        intent_frame_v1=dict(input_payload.get("intent_frame_v1") or {}),
                    )
                else:
                    result = await graph.resume(thread_id=task.thread_id or str(task.id), approved=approved)
        except AgentTaskCancelled:
            await self.db.rollback()
            return {"status": "cancelled", "final_answer": "任务已由用户取消。"}
        except Exception as exc:
            await self.db.rollback()
            await self._mark_failed(task_id, exc)
            raise

        await self._finish_task(task_id, result)
        # Terminal state and persisted reply must become visible before completion is emitted.
        for event_type, state, payload in terminal_events:
            await self._record_event(task_id, registry, event_type, state, payload)
        return result

    async def _load_context(
        self, task: AgentTask, user: User, *, history_context: ConversationContext | None = None,
    ) -> dict[str, Any]:
        from app.services.memory_retrieval_service import MemoryRetrievalService
        from app.services.conversation_constraints import render_session_constraints
        from app.services.profile_context_cache import ProfileContextCache
        from app.services.profile_service import ProfileService

        profile = await ProfileContextCache().get_or_load(
            user.id,
            lambda: ProfileService(self.db).get_summary(user.id),
        )
        memories = await MemoryRetrievalService(self.db).retrieve(
            user_id=user.id, course_id=task.course_id, question=task.task_goal, limit=5,
        )
        return {
            "profile": profile.model_dump(mode="json"),
            "memories": [item.model_dump(mode="json") for item in memories],
            "conversation_summary": (
                "\n".join(filter(None, [
                    history_context.summary,
                    "较早学生原话：" + "；".join(history_context.older_user_requests)
                    if history_context.older_user_requests else "",
                ]))[:2400] if history_context is not None else ""
            ),
            "session_constraints": (
                render_session_constraints(history_context.active_constraints)
                if history_context is not None else ""
            ),
            "course_id": str(task.course_id),
        }

    async def _record_event(
        self,
        task_id: UUID,
        registry,
        event_type: str,
        state: dict[str, Any],
        payload: dict[str, Any],
    ) -> None:
        current = await self._get_task_optional(task_id)
        if current is None:
            return
        if current.status == "cancelled":
            raise AgentTaskCancelled("Agent task was cancelled")
        event = await self.conversations.add_event(
            task_id=current.id,
            conversation_id=current.conversation_id,
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
        elif event_type == "failed":
            values["status"] = "failed"
        await self.tasks.update_task(current, **values)

        if event_type == "tool_started":
            tool_call_id = str(payload.get("tool_call_id") or "")
            operation = payload.get("operation_key")
            prior_operation = await self.tasks.get_step_by_operation(current.id, str(operation)) if operation else None
            if tool_call_id and prior_operation is None and await self.tasks.get_step_by_tool_call(current.id, tool_call_id) is None:
                tool = registry.get(str(payload["tool_name"]))
                await self.tasks.create_dynamic_step(
                    task_id=current.id,
                    step_index=len(await self.tasks.list_steps(current.id)) + 1,
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
                    operation_key=operation,
                )
        elif event_type == "tool_completed":
            tool_call_id = str(payload.get("tool_call_id") or "")
            duration_ms = payload.get("duration_ms")
            if tool_call_id and isinstance(duration_ms, int):
                step = await self.tasks.get_step_by_tool_call(current.id, tool_call_id)
                if step is not None:
                    await self.tasks.update_step(step, duration_ms=duration_ms)
        await self.db.commit()
        await self.broker.publish(current.id, event_type, {**payload, "sequence_no": event.sequence_no})

    async def _mark_failed(self, task_id: UUID, exc: Exception) -> None:
        current = await self._get_task_optional(task_id)
        if current is None or current.status in {"cancelled", "succeeded"}:
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

    async def _publish_direct_completion(self, task_id: UUID, result: dict[str, Any]) -> None:
        current = await self._get_task(task_id)
        if current.status != "succeeded":
            return
        payload = {
            "status": "completed",
            "final_answer": extract_final_answer_text(result.get("final_answer") or ""),
            "artifacts": result.get("artifacts") or [],
            "citations": result.get("citations") or [],
        }
        event = await self.conversations.add_event(
            task_id=current.id,
            conversation_id=current.conversation_id,
            event_type="completed",
            payload=payload,
        )
        await self.db.commit()
        await self.broker.publish(current.id, "completed", {**payload, "sequence_no": event.sequence_no})

    async def _load_tool_result(self, key: str) -> ToolExecutionResult | None:
        task_id, tool_call_id = key.split(":", 1)
        step = await self.tasks.get_step_by_operation(UUID(task_id), tool_call_id) if tool_call_id.startswith("op:") else await self.tasks.get_step_by_tool_call(UUID(task_id), tool_call_id)
        if step is not None and tool_call_id.startswith("op:") and step.status == "running":
            return ToolExecutionResult(success=False, error_message="上次业务操作的提交结果未知，已阻止重复执行；请核对任务产物后重新发起明确请求。")
        if step is None or step.status not in {"succeeded", "failed"}:
            return None
        output = dict(step.output_payload or {})
        citations = output.pop("_citations", [])
        final_answer = output.pop("_final_answer", None)
        return ToolExecutionResult(
            success=step.status == "succeeded",
            output=output,
            evidence=step.evidence,
            artifact_refs=step.artifact_refs,
            citations=citations,
            error_message=step.error_message,
            attempts=step.retry_count + 1,
            final_answer=final_answer,
        )

    async def _save_tool_result(self, key: str, result: ToolExecutionResult) -> None:
        task_id, tool_call_id = key.split(":", 1)
        step = await self.tasks.get_step_by_operation(UUID(task_id), tool_call_id) if tool_call_id.startswith("op:") else await self.tasks.get_step_by_tool_call(UUID(task_id), tool_call_id)
        if step is None:
            return
        output_payload = dict(result.output or {})
        if result.citations:
            output_payload["_citations"] = result.citations
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
            duration_ms=getattr(result, "duration_ms", None),
            finished_at=datetime.now(UTC),
        )
        await self.db.commit()

    async def _finish_task(self, task_id: UUID, result: dict[str, Any]) -> None:
        current = await self._get_task(task_id)
        if current.status == "cancelled":
            return
        status = result.get("status")
        intent_frame = dict((current.input_payload or {}).get("intent_frame_v1") or {})
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
                "intent_frame_v1": intent_frame,
                "subtask_progress_v1": subtask_progress(intent_frame, result),
            },
        }
        if status == "completed":
            values.update(status="succeeded", finished_at=datetime.now(UTC), error_message=None)
            qa_output = self._grounded_qa_output(result)
            answer_metadata = dict(result.get("answer_generation_metadata") or {})
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
                    "learning_record_id": qa_output.get("message_id"),
                    "grounding_status": qa_output.get("grounding_status"),
                    "grounding_message": qa_output.get("grounding_message"),
                    "follow_up_questions": qa_output.get("follow_up_questions") or [],
                    "related_knowledge_points": qa_output.get("related_knowledge_points") or [],
                    "provider": qa_output.get("provider") or answer_metadata.get("provider") or result.get("provider"),
                    "model": qa_output.get("model") or answer_metadata.get("model"),
                    "answer_source": "grounded_qa" if qa_output else "supervisor" if answer_metadata else "rule",
                    "fallback_used": bool(qa_output.get("fallback_used") or answer_metadata.get("fallback_used")),
                    "failed_provider": qa_output.get("failed_provider"),
                    "fallback_reason": qa_output.get("fallback_reason"),
                    "performance": qa_output.get("performance") or {},
                    "postprocess_status": qa_output.get("postprocess_status") or "skipped",
                    "knowledge_extract": qa_output.get("knowledge_extract") or {},
                    "graph_context": qa_output.get("graph_context") or {},
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
        if status == "completed" and intent_frame.get("mode") == "clarify":
            return
        if status == "completed" and result.get("direct_reference"):
            try:
                from app.services.conversation_summary_service import ConversationSummaryService

                await ConversationSummaryService(self.db).maybe_compact(
                    conversation_id=current.conversation_id, user_id=current.user_id,
                )
            except Exception:
                await self.db.rollback()
            return
        if status == "completed":
            qa_output = self._grounded_qa_output(result)
            if (
                not qa_output
                or not qa_output.get("message_id")
                or qa_output.get("postprocess_status") != "queued"
            ):
                await self._publish_chat_completed(current, result)
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
            try:
                from app.services.conversation_summary_service import ConversationSummaryService

                await ConversationSummaryService(self.db).maybe_compact(
                    conversation_id=current.conversation_id, user_id=current.user_id,
                )
            except Exception:
                await self.db.rollback()

    def _grounded_qa_output(self, result: dict[str, Any]) -> dict[str, Any]:
        for observation in reversed(result.get("observations") or []):
            if observation.get("success") and observation.get("tool_name") == "answer_course_question":
                return dict(observation.get("output") or {})
        return {}

    async def _publish_chat_completed(self, task: AgentTask, result: dict[str, Any]) -> None:
        question = str(task.task_goal or (task.input_payload or {}).get("user_input") or "").strip()
        answer = extract_final_answer_text(result.get("final_answer") or "").strip()
        if not question or not answer:
            return
        from app.services.chat_knowledge_pipeline import publish_chat_completed

        await publish_chat_completed(
            user_id=task.user_id,
            course_id=task.course_id,
            question=question,
            answer=answer,
            citations=list(result.get("citations") or []),
            message_id=str(task.id),
            source="agent_runtime_service",
        )

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
