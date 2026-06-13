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
    ) -> list[AgentMessageRead]:
        conversation = await self._get_owned_conversation(conversation_id, current_user.id)
        return [
            AgentMessageRead.model_validate(item)
            for item in await self.conversations.list_messages(conversation.id)
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
        message = await self.conversations.add_message(
            conversation=conversation,
            user_id=current_user.id,
            role="user",
            content=payload.content,
        )
        task = await self.tasks.create_dynamic_task(
            user_id=current_user.id,
            course_id=conversation.course_id,
            conversation_id=conversation.id,
            thread_id=conversation.thread_id,
            goal=payload.content,
        )
        planned_tools = supervisor_intents.plan_required_tools(
            payload.content,
            is_profile_update_only=False,
        )
        tool_topics = supervisor_intents.parse_tool_topics(payload.content)
        parsed_intents = [
            {
                "segment": item.segment,
                "topic": item.topic,
                "tools": list(item.tools),
            }
            for item in supervisor_intents.parse_goal_intents(payload.content)
        ]
        tool_hints = list(payload.tool_hints or [])
        for name in planned_tools:
            if name not in tool_hints:
                tool_hints.append(name)
        await self.tasks.update_task(
            task,
            input_payload={
                "user_input": payload.content,
                "tool_hints": tool_hints,
                "skip_tools": list(payload.skip_tools or []),
                "planned_tools": planned_tools,
                "tool_topics": tool_topics,
                "parsed_intents": parsed_intents,
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
        await self.db.commit()
        await self.db.refresh(conversation)
        await self.db.refresh(message)
        await self.db.refresh(task)
        try:
            queued = await self.queue.enqueue(task.id)
        except Exception:
            queued = False
        if not queued:
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
        return AgentTaskRead.model_validate(await self._get_owned_task(task_id, current_user.id))

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
