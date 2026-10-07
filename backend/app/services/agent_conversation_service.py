from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.agent_conversation import AgentConversation
from app.models.agent_task import AgentTask
from app.models.user import User
from app.repositories.agent_conversation_repository import AgentConversationRepository
from app.repositories.agent_task_repository import AgentTaskRepository
from app.agent_runtime import supervisor_intents
from app.agent_runtime.intent_contract import build_intent_frame, follow_up_topic, looks_like_topic_answer
from app.schemas.agent_conversation import (
    AgentConversationCreateRequest,
    AgentConversationRead,
    AgentMessageAccepted,
    AgentMessageCreateRequest,
    AgentMessageRead,
    AgentTaskEventRead,
)
from app.schemas.agent_task import AgentTaskRead
from app.services.agent_inline_runner import schedule_inline_fallback
from app.services.agent_queue_service import AgentEventBroker, AgentQueueService
from app.services.course_service import CourseService
from app.services.conversation_context_service import ConversationContextService
from app.services.conversation_intent import is_simple_greeting


class AgentConversationService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        queue: AgentQueueService | None = None,
        broker: AgentEventBroker | None = None,
    ) -> None:
        self.db = db
        self.conversations = AgentConversationRepository(db)
        self.tasks = AgentTaskRepository(db)
        self.queue = queue or AgentQueueService()
        self.broker = broker or AgentEventBroker()

    async def create_conversation(
        self,
        payload: AgentConversationCreateRequest,
        current_user: User,
    ) -> AgentConversationRead:
        await CourseService(self.db).get_readable_course(payload.course_id, current_user)
        conversation = await self.conversations.create(
            user_id=current_user.id,
            course_id=payload.course_id,
            title=payload.title,
        )
        await self.db.commit()
        await self.db.refresh(conversation)
        return AgentConversationRead.model_validate(conversation)

    async def list_conversations(self, current_user: User) -> list[AgentConversationRead]:
        items = await self.conversations.list_for_user(current_user.id)
        return [AgentConversationRead.model_validate(item) for item in items]

    async def list_messages(
        self,
        conversation_id: UUID,
        current_user: User,
        *,
        limit: int = 40,
    ) -> list[AgentMessageRead]:
        conversation = await self._get_owned_conversation(conversation_id, current_user.id)
        return [
            AgentMessageRead.model_validate(item)
            for item in await self.conversations.list_messages(conversation.id, limit=limit)
        ]

    async def send_message(
        self,
        conversation_id: UUID,
        payload: AgentMessageCreateRequest,
        current_user: User,
    ) -> AgentMessageAccepted:
        conversation = await self._get_owned_conversation(conversation_id, current_user.id)
        if conversation.course_id is None:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="当前会话缺少课程上下文",
                status_code=400,
            )
        await CourseService(self.db).get_readable_course(conversation.course_id, current_user)
        conversation = await self.conversations.get_for_user_locked(conversation.id, current_user.id)
        if conversation is None:
            raise BusinessException(code=ErrorCode.NOT_FOUND, detail="会话不存在", status_code=404)
        current_text = payload.content.strip()
        draft = dict((conversation.extra_meta or {}).get("intent_draft_v1") or {})
        current_intents = supervisor_intents.parse_goal_intents(payload.content)
        repeat_clarification = bool(draft and current_text in {"好", "可以", "是的", "继续"})
        is_topic_reply = bool(
            draft and not current_intents and looks_like_topic_answer(current_text)
            and current_text not in {"算了", "取消", "不用了", "换个话题", "好", "可以", "是的", "继续"}
            and not is_simple_greeting(current_text)
        )
        reuse_draft = is_topic_reply or repeat_clarification
        semantic_reply = bool(draft.get("kind") == "semantic" and not current_intents
                              and current_text not in {"取消", "算了", "不用了", "换个话题"}
                              and not is_simple_greeting(current_text))
        reuse_draft = reuse_draft or semantic_reply
        effective_goal = str(draft.get("goal") or "") if reuse_draft else payload.content
        if semantic_reply and not repeat_clarification:
            effective_goal += "\n学生补充要求：" + current_text
        origin_message_id = UUID(str(draft["request_message_id"])) if reuse_draft else None
        revision = int(draft.get("revision") or 1) + 1 if reuse_draft else 1
        fallback_topic = None
        if is_topic_reply and not semantic_reply:
            fallback_topic = current_text
        elif current_text.startswith(("再", "继续", "刚才", "上面", "这个", "那个", "同类")):
            context = await ConversationContextService(self.db).load(
                conversation_id=conversation.id,
                user_id=current_user.id,
                course_id=conversation.course_id,
            )
            fallback_topic = follow_up_topic(
                goal=payload.content, previous_question=context.last_question,
            )
        candidate_intents = supervisor_intents.parse_goal_intents(effective_goal)
        if len(candidate_intents) > 8:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="单次请求最多支持 8 个交付子任务，请分批提交",
                status_code=400,
            )
        request_payload = {
            "content": payload.content,
            "tool_hints": list(payload.tool_hints or []),
            "skip_tools": list(payload.skip_tools or []),
        }
        if payload.revises_task_id:
            request_payload["revises_task_id"] = str(payload.revises_task_id)
        if payload.client_request_id is not None:
            existing = await self.conversations.get_request_message(conversation.id, payload.client_request_id)
            if existing is not None:
                if existing.payload.get("request_payload") != request_payload:
                    raise BusinessException(
                        code=ErrorCode.CONFLICT, detail="同一请求 ID 的消息内容不一致", status_code=409,
                    )
                if existing.task_id is None:
                    raise BusinessException(
                        code=ErrorCode.CONFLICT, detail="原请求尚未完成任务关联", status_code=409,
                    )
                task = await self._get_owned_task(existing.task_id, current_user.id)
                return AgentMessageAccepted(
                    conversation=AgentConversationRead.model_validate(conversation),
                    message=AgentMessageRead.model_validate(existing),
                    task=AgentTaskRead.model_validate(task),
                    queued=task.status in {"queued", "running", "planned"},
                )
        if payload.revises_task_id:
            previous = await self._get_owned_task(payload.revises_task_id, current_user.id)
            if previous.conversation_id != conversation.id:
                raise BusinessException(code=ErrorCode.NOT_FOUND, detail="修订目标不属于当前会话", status_code=404)
            if previous.status not in {"cancelled", "failed", "succeeded"} or any(
                step.status == "running" for step in await self.tasks.list_steps(previous.id)
            ):
                raise BusinessException(code=ErrorCode.CONFLICT, detail="请先停止原任务并等待正在执行的步骤结束，再提交修订", status_code=409)
            previous_frame = (previous.input_payload or {}).get("intent_frame_v1") or {}
            effective_goal = (previous_frame.get("resolved_goal") or previous.task_goal) + "\n学生最新修订（优先于之前要求）：" + payload.content
            revision = int(previous_frame.get("revision") or 1) + 1
            source_message_id = previous_frame.get("original_request_message_id") or previous_frame.get("request_message_id")
            origin_message_id = UUID(source_message_id) if source_message_id else None
            fallback_topic = None
        message = await self.conversations.add_message(
            conversation=conversation,
            user_id=current_user.id,
            role="user",
            content=payload.content,
            client_request_id=payload.client_request_id,
            payload={"request_payload": request_payload} if payload.client_request_id else None,
        )
        intent_frame = build_intent_frame(
            goal=effective_goal, request_message_id=message.id,
            skip_tools=list(payload.skip_tools or []),
            fallback_topic=fallback_topic,
            original_request_message_id=origin_message_id,
            revision=revision,
        ).model_dump(mode="json")
        if intent_frame["mode"] == "clarify":
            conversation.extra_meta = {
                **(conversation.extra_meta or {}),
                "intent_draft_v1": {
                    "goal": effective_goal,
                    "request_message_id": str(origin_message_id or message.id),
                    "revision": revision,
                },
            }
        elif draft:
            conversation.extra_meta = {
                key: value for key, value in (conversation.extra_meta or {}).items()
                if key != "intent_draft_v1"
            }
        task = await self.tasks.create_dynamic_task(
            user_id=current_user.id,
            course_id=conversation.course_id,
            conversation_id=conversation.id,
            thread_id=conversation.thread_id,
            goal=effective_goal,
        )
        planned_tools = supervisor_intents.plan_required_tools(
            effective_goal,
            is_profile_update_only=False,
        )
        tool_topics = supervisor_intents.parse_tool_topics(effective_goal)
        for item in intent_frame["tasks"]:
            for name in item["tools"]:
                tool_topics.setdefault(name, item["topic"])
                if fallback_topic and item["topic"] == fallback_topic:
                    tool_topics[name] = fallback_topic
        parsed_intents = [
            {
                "segment": item["segment"],
                "topic": item["topic"],
                "tools": item["tools"],
            }
            for item in intent_frame["tasks"]
        ]
        await self.tasks.update_task(
            task,
            input_payload={
                "user_input": payload.content,
                "resolved_goal": effective_goal,
                "tool_hints": list(payload.tool_hints or []),
                "inferred_tool_candidates": planned_tools,
                "intent_frame_v1": intent_frame,
                "needs_context_disambiguation": intent_frame["mode"] == "clarify" and int(getattr(message, "sequence_no", 0) or 0) > 1,
                "skip_tools": list(payload.skip_tools or []),
                "planned_tools": planned_tools,
                "tool_topics": tool_topics,
                "parsed_intents": parsed_intents,
                **({"revises_task_id": str(payload.revises_task_id)} if payload.revises_task_id else {}),
            },
            plan_json={
                "intent_frame_v1": intent_frame,
                "subtask_progress_v1": [
                    {"subtask_id": item["id"], "status": "pending", "artifact_refs": []}
                    for item in intent_frame["tasks"]
                ],
            },
        )
        message.task_id = task.id
        if conversation.title == "新对话":
            conversation.title = payload.content[:40]
        event = await self.conversations.add_event(
            task_id=task.id,
            conversation_id=conversation.id,
            event_type="queued",
            payload={"message": "任务已进入持久后台队列"},
        )
        if intent_frame["tasks"]:
            await self.conversations.add_event(
                task_id=task.id,
                conversation_id=conversation.id,
                event_type="intent_resolved",
                payload={
                    "schema_version": "v1",
                    "parser": intent_frame["parser"],
                    "tasks": [
                        {"id": item["id"], "topic": item["topic"], "tools": item["tools"]}
                        for item in intent_frame["tasks"]
                    ],
                },
            )
        if intent_frame["mode"] == "clarify":
            await self.conversations.add_event(
                task_id=task.id,
                conversation_id=conversation.id,
                event_type="clarification_requested",
                payload={"question": intent_frame["clarification_question"], "slots": intent_frame["unresolved_slots"]},
            )
        await self.db.commit()
        await self.db.refresh(conversation)
        await self.db.refresh(message)
        await self.db.refresh(task)
        try:
            queued = await self.queue.enqueue(task.id)
        except Exception:
            queued = False
        if not queued:
            self._clear_matching_intent_draft(conversation, task)
            await self.tasks.update_task(
                task,
                status="failed",
                error_message="任务队列拒绝了重复或无效任务",
                finished_at=datetime.now(UTC),
            )
            await self.db.commit()
            raise BusinessException(
                code=ErrorCode.AGENT_RUN_FAILED,
                detail="Agent 后台任务入队失败",
                status_code=503,
            )
        await self.broker.publish(task.id, "queued", {"sequence_no": event.sequence_no})
        schedule_inline_fallback(task.id)
        return AgentMessageAccepted(
            conversation=AgentConversationRead.model_validate(conversation),
            message=AgentMessageRead.model_validate(message),
            task=AgentTaskRead.model_validate(task),
            queued=True,
        )

    async def get_task(self, task_id: UUID, current_user: User) -> AgentTaskRead:
        task = await self._get_owned_task(task_id, current_user.id)
        settled = not any(step.status == "running" for step in await self.tasks.list_steps(task.id))
        return AgentTaskRead.model_validate(task).model_copy(update={"execution_settled": settled})

    async def list_events(self, task_id: UUID, current_user: User) -> list[AgentTaskEventRead]:
        task = await self._get_owned_task(task_id, current_user.id)
        return [
            AgentTaskEventRead.model_validate(item)
            for item in await self.conversations.list_events(task.id)
        ]

    async def resume_task(
        self,
        task_id: UUID,
        current_user: User,
        *,
        approved: bool,
    ) -> AgentTaskRead:
        task = await self._get_owned_task(task_id, current_user.id)
        if task.status != "waiting_confirmation":
            raise BusinessException(
                code=ErrorCode.CONFLICT,
                detail="只有等待确认的 Agent 任务可以恢复",
                status_code=409,
            )
        await self.tasks.update_task(
            task,
            status="queued",
            confirmed_at=datetime.now(UTC) if approved else None,
        )
        await self.db.commit()
        try:
            queued = await self.queue.enqueue(task.id, approved=approved)
        except Exception:
            queued = False
        if not queued:
            await self.tasks.update_task(
                task,
                status="failed",
                error_message="Agent 恢复任务入队失败",
                finished_at=datetime.now(UTC),
            )
            await self.db.commit()
            raise BusinessException(
                code=ErrorCode.AGENT_RUN_FAILED,
                detail="Agent 恢复任务入队失败",
                status_code=503,
            )
        schedule_inline_fallback(task.id)
        return AgentTaskRead.model_validate(task)

    async def cancel_task(self, task_id: UUID, current_user: User) -> AgentTaskRead:
        task = await self._get_owned_task(task_id, current_user.id)
        if task.status not in {"queued", "planned", "waiting_confirmation", "running"}:
            raise BusinessException(
                code=ErrorCode.CONFLICT,
                detail="当前 Agent 任务不可取消",
                status_code=409,
            )
        await self.tasks.update_task(
            task,
            status="cancelled",
            cancelled_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )
        if (task.input_payload or {}).get("intent_frame_v1", {}).get("mode") == "clarify":
            conversation = await self.conversations.get_for_user_locked(task.conversation_id, current_user.id)
            if conversation is not None:
                self._clear_matching_intent_draft(conversation, task)
        event = await self.conversations.add_event(
            task_id=task.id,
            conversation_id=task.conversation_id,
            event_type="cancelled",
            payload={"message": "用户取消任务"},
        )
        await self.db.commit()
        await self.db.refresh(task)
        await self.broker.publish(task.id, "cancelled", {"sequence_no": event.sequence_no})
        return AgentTaskRead.model_validate(task)

    @staticmethod
    def _clear_matching_intent_draft(conversation: AgentConversation, task: AgentTask) -> None:
        frame = dict((task.input_payload or {}).get("intent_frame_v1") or {})
        if frame.get("mode") != "clarify":
            return
        draft = dict((conversation.extra_meta or {}).get("intent_draft_v1") or {})
        source_id = frame.get("original_request_message_id") or frame.get("request_message_id")
        if str(draft.get("request_message_id") or "") != str(source_id or ""):
            return
        if int(draft.get("revision") or 0) != int(frame.get("revision") or 0):
            return
        conversation.extra_meta = {
            key: value for key, value in (conversation.extra_meta or {}).items()
            if key != "intent_draft_v1"
        }

    async def requeue_task(self, task_id: UUID, current_user: User) -> AgentTaskRead:
        task = await self._get_owned_task(task_id, current_user.id)
        if task.status != "queued" or task.started_at is not None:
            raise BusinessException(
                code=ErrorCode.CONFLICT,
                detail="只有尚未被 Worker 接管的 queued 任务可以重新入队",
                status_code=409,
            )
        try:
            queued = await self.queue.enqueue(task.id, replace=True)
        except Exception:
            queued = False
        if not queued:
            raise BusinessException(
                code=ErrorCode.AGENT_RUN_FAILED,
                detail="Agent 任务重新入队失败，请确认 arq Worker 已启动",
                status_code=503,
            )
        event = await self.conversations.add_event(
            task_id=task.id,
            conversation_id=task.conversation_id,
            event_type="queued",
            payload={"message": "任务已重新入队，等待 Worker 接管"},
        )
        await self.db.commit()
        await self.broker.publish(
            task.id,
            "queued",
            {"sequence_no": event.sequence_no, "requeued": True},
        )
        schedule_inline_fallback(task.id)
        return AgentTaskRead.model_validate(task)

    async def _get_owned_conversation(self, conversation_id: UUID, user_id: UUID) -> AgentConversation:
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if conversation is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="Agent 会话不存在",
                status_code=404,
            )
        return conversation

    async def _get_owned_task(self, task_id: UUID, user_id: UUID) -> AgentTask:
        task = await self.tasks.get_for_user(task_id, user_id)
        if task is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="Agent 任务不存在",
                status_code=404,
            )
        return task
