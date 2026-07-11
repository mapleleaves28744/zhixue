from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.event_bus import Event
from app.services.agent_service import AgentService
from app.services.memory_service import MemoryService


class TutorPostprocessService:
    """Run non-critical deep Tutor processing after the answer is committed."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def run(self, event: Event) -> None:
        user_id = UUID(str(event.data["user_id"]))
        course_id = UUID(str(event.data["course_id"]))
        answer = str(event.data.get("answer") or "")
        citations = list(event.data.get("citations") or [])
        await AgentService(self.db).run_task(
            task_type="review_content",
            user_id=user_id,
            course_id=course_id,
            params={"content": str({"answer": answer, "citations": citations})[:4000]},
        )
        await MemoryService(self.db).reflect(user_id, course_id)
        await self.db.commit()
