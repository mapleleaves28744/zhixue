from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_conversation import AgentConversation, AgentMessage, AgentTaskEvent


class AgentConversationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search_owned_history(self, *, user_id: UUID, course_id: UUID, query: str,
                                   conversation_id: UUID | None, before_sequence: int | None,
                                   limit: int = 40) -> list[AgentMessage]:
        from sqlalchemy import or_

        statement = select(AgentMessage).join(AgentConversation).where(
            AgentMessage.user_id == user_id, AgentConversation.user_id == user_id,
            AgentConversation.course_id == course_id, AgentMessage.role.in_(["user", "assistant"]),
            AgentMessage.content.contains(query, autoescape=True),
        )
        if conversation_id and before_sequence is not None:
            statement = statement.where(or_(AgentMessage.conversation_id != conversation_id,
                                           AgentMessage.sequence_no < before_sequence))
        return list((await self.db.execute(statement.order_by(AgentMessage.created_at.desc())
                                           .limit(min(limit, 100)))).scalars().all())

    async def suppressed_history_message_ids(self, *, user_id: UUID, course_id: UUID,
                                              source_ids: set[str]) -> set[UUID]:
        if not source_ids:
            return set()
        rows = list((await self.db.execute(select(AgentMessage).join(AgentConversation).where(
            AgentMessage.user_id == user_id, AgentConversation.user_id == user_id,
            AgentConversation.course_id == course_id, AgentMessage.role == "assistant",
            AgentMessage.payload["learning_record_id"].astext.in_(source_ids),
        ))).scalars().all())
        hidden = {row.id for row in rows}
        for row in rows:
            key = (AgentMessage.task_id == row.task_id if row.task_id else
                   AgentMessage.client_request_id == row.client_request_id if row.client_request_id else
                   AgentMessage.sequence_no == row.sequence_no - 1)
            ids = (await self.db.execute(select(AgentMessage.id).where(
                AgentMessage.user_id == user_id, AgentMessage.conversation_id == row.conversation_id,
                AgentMessage.role == "user", key,
            ))).scalars().all()
            hidden.update(ids)
        return hidden

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

    async def get_for_user_locked(self, conversation_id: UUID, user_id: UUID) -> AgentConversation | None:
        result = await self.db.execute(select(AgentConversation).where(
            AgentConversation.id == conversation_id,
            AgentConversation.user_id == user_id,
        ).with_for_update().execution_options(populate_existing=True))
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
        client_request_id: UUID | None = None,
        message_type: str = "text",
        payload: dict[str, Any] | None = None,
    ) -> AgentMessage:
        locked = (await self.db.execute(
            select(AgentConversation).where(AgentConversation.id == conversation.id).with_for_update()
        )).scalar_one()
        locked.next_message_sequence += 1
        message = AgentMessage(
            conversation_id=conversation.id,
            user_id=user_id,
            task_id=task_id,
            client_request_id=client_request_id,
            sequence_no=locked.next_message_sequence,
            role=role,
            message_type=message_type,
            content=content,
            payload=payload or {},
        )
        self.db.add(message)
        now = datetime.now(UTC)
        locked.last_message_at = now
        locked.updated_at = now
        await self.db.flush()
        return message

    async def list_messages(
        self, conversation_id: UUID, limit: int = 40, *, before_sequence: int | None = None,
    ) -> list[AgentMessage]:
        statement = select(AgentMessage).where(AgentMessage.conversation_id == conversation_id)
        if before_sequence is not None:
            statement = statement.where(AgentMessage.sequence_no < before_sequence)
        result = await self.db.execute(statement.order_by(AgentMessage.sequence_no.desc()).limit(limit))
        # Fetch the newest page efficiently, then keep the chronological order expected by clients.
        return list(reversed(result.scalars().all()))

    async def list_messages_after_sequence(
        self, conversation_id: UUID, after_sequence: int, *, limit: int = 120,
    ) -> list[AgentMessage]:
        result = await self.db.execute(select(AgentMessage).where(
            AgentMessage.conversation_id == conversation_id,
            AgentMessage.sequence_no > after_sequence,
        ).order_by(AgentMessage.sequence_no.asc()).limit(limit))
        return list(result.scalars().all())

    async def get_request_message(self, conversation_id: UUID, client_request_id: UUID) -> AgentMessage | None:
        return (await self.db.execute(select(AgentMessage).where(
            AgentMessage.conversation_id == conversation_id,
            AgentMessage.client_request_id == client_request_id,
        ))).scalar_one_or_none()

    async def get_message_by_sequence(self, conversation_id: UUID, sequence_no: int) -> AgentMessage | None:
        return (await self.db.execute(select(AgentMessage).where(
            AgentMessage.conversation_id == conversation_id,
            AgentMessage.sequence_no == sequence_no,
        ))).scalar_one_or_none()

    async def get_task_user_message(self, conversation_id: UUID, task_id: UUID) -> AgentMessage | None:
        return (await self.db.execute(select(AgentMessage).where(
            AgentMessage.conversation_id == conversation_id,
            AgentMessage.task_id == task_id,
            AgentMessage.role == "user",
        ).order_by(AgentMessage.sequence_no.asc()).limit(1))).scalar_one_or_none()

    async def invalidate_context_summaries(self, *, user_id: UUID, course_id: UUID | None) -> None:
        statement = update(AgentConversation).where(AgentConversation.user_id == user_id)
        if course_id is not None:
            statement = statement.where(AgentConversation.course_id == course_id)
        await self.db.execute(statement.values(
            summary=None,
            extra_meta=AgentConversation.extra_meta.op("-")("context_compaction_v1"),
        ))

    async def add_event(
        self,
        *,
        task_id: UUID,
        conversation_id: UUID | None,
        event_type: str,
        payload: dict[str, Any],
    ) -> AgentTaskEvent:
        for attempt in range(3):
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
            try:
                await self.db.flush()
                return event
            except IntegrityError as exc:
                await self.db.rollback()
                if attempt >= 2:
                    raise RuntimeError("failed to append agent task event") from exc

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
