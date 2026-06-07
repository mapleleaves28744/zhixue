from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.rag.hybrid_retriever import HybridRetriever
from app.services.course_service import CourseService


class KnowledgeSearchService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(
        self,
        *,
        current_user: User,
        course_id: UUID,
        query: str,
        top_k: int = 5,
        knowledge_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        await CourseService(self.db).get_readable_course(course_id, current_user)
        results = await HybridRetriever(self.db).search(
            course_id=course_id,
            query=query,
            user_id=None if current_user.role == "admin" else current_user.id,
            top_k=top_k,
            knowledge_id=knowledge_id,
        )
        return [
            {
                "chunk_id": str(item.chunk_id),
                "material_id": str(item.material_id),
                "content": item.content,
                "source_title": item.source_title,
                "page_no": item.page_no,
                "score": round(item.score, 6),
                "retrieval_mode": item.retrieval_mode,
                "extra_meta": item.extra_meta,
            }
            for item in results
        ]
