from __future__ import annotations

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.agent_conversation_repository import AgentConversationRepository
from app.services.memory_suppression_service import MemorySuppressionService


class ConversationHistoryService:
    """Bounded historical excerpts, always restricted to this student and course."""
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(self, *, user_id: UUID, course_id: UUID, query: str,
                     conversation_id: UUID | None = None, task_id: UUID | None = None,
                     limit: int = 8) -> list[dict]:
        query = query.strip()
        if not query or len(query) > 120:
            return []
        repository = AgentConversationRepository(self.db)
        task_message = await repository.get_task_user_message(conversation_id, task_id) if conversation_id and task_id else None
        if conversation_id and task_id and task_message is None:
            return []
        rows = await repository.search_owned_history(
            user_id=user_id, course_id=course_id, query=query, conversation_id=conversation_id,
            before_sequence=task_message.sequence_no if task_message else None,
        )
        suppressed = await MemorySuppressionService(self.db).source_record_ids(user_id=user_id, course_id=course_id)
        hidden = await repository.suppressed_history_message_ids(user_id=user_id, course_id=course_id, source_ids=suppressed)
        items = []
        for row in rows:
            if row.id in hidden:
                continue
            items.append({"message_id": str(row.id), "conversation_id": str(row.conversation_id),
                          "sequence_no": row.sequence_no, "role": row.role,
                          "excerpt": row.content[:600], "created_at": row.created_at.isoformat()})
            if len(items) >= min(max(limit, 1), 8):
                break
        return items
