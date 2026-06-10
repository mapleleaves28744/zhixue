from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_conversation import AgentConversation, AgentMessage, AgentTaskEvent


class AgentConversationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        title: str | None = None,
    ) -> AgentConversation:
        conversation = AgentConversation(
            user_id=user_id,
            course_id=course_id,
            thread_id=f"agent-{uuid4()}",
            title=(title or "新对话")[:255],
        )
        self.db.add(conversation)
        await self.db.flush()
        return conversation

    async def get_for_user(self, conversation_id: UUID, user_id: UUID) -> AgentConversation | None:
        result = await self.db.execute(
            select(AgentConversation).where(
                AgentConversation.id == conversation_id,
                AgentConversation.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: UUID, limit: int = 50) -> list[AgentConversation]:
        result = await self.db.execute(
            select(AgentConversation)
            .where(AgentConversation.user_id == user_id)
            .order_by(AgentConversation.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def add_message(
        self,
        *,
        conversation: AgentConversation,
        user_id: UUID,
        role: str,
        content: str,
        task_id: UUID | None = None,
        message_type: str = "text",
        payload: dict[str, Any] | None = None,
    ) -> AgentMessage:
        message = AgentMessage(
            conversation_id=conversation.id,
            user_id=user_id,
            task_id=task_id,
            role=role,
            message_type=message_type,
            content=content,
            payload=payload or {},
        )
        self.db.add(message)
        now = datetime.now(UTC)
        conversation.last_message_at = now
        conversation.updated_at = now
        await self.db.flush()
        return message

    async def list_messages(self, conversation_id: UUID, limit: int = 100) -> list[AgentMessage]:
        result = await self.db.execute(
            select(AgentMessage)
            .where(AgentMessage.conversation_id == conversation_id)
            .order_by(AgentMessage.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def add_event(
        self,
        *,
        task_id: UUID,
        conversation_id: UUID | None,
        event_type: str,
        payload: dict[str, Any],
    ) -> AgentTaskEvent:
        current = (
            await self.db.execute(
                select(func.max(AgentTaskEvent.sequence_no)).where(AgentTaskEvent.task_id == task_id)
            )
        ).scalar()
        event = AgentTaskEvent(
            task_id=task_id,
            conversation_id=conversation_id,
            sequence_no=int(current or 0) + 1,
            event_type=event_type,
            payload=payload,
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def list_events(self, task_id: UUID, after_sequence: int = 0) -> list[AgentTaskEvent]:
        result = await self.db.execute(
            select(AgentTaskEvent)
            .where(
                AgentTaskEvent.task_id == task_id,
                AgentTaskEvent.sequence_no > after_sequence,
            )
            .order_by(AgentTaskEvent.sequence_no.asc())
        )
        return list(result.scalars().all())
