from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.knowledge_search_service import KnowledgeSearchService
from app.services.profile_service import ProfileService


class MultimodalBriefService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def build_brief(
        self,
        *,
        current_user: User,
        course_id: UUID,
        topic: str,
        modality: str,
        requirement: str | None = None,
        top_k: int = 6,
    ) -> dict[str, Any]:
        profile = await ProfileService(self.db).get_profile(current_user.id)
        search_items = await KnowledgeSearchService(self.db).search(
            current_user=current_user,
            course_id=course_id,
            query=topic,
            top_k=top_k,
        )
        citations = [
            {
                "source_type": "document",
                "title": item.get("source_title") or "课程资料",
                "source_id": item.get("material_id"),
                "chunk_id": item.get("chunk_id"),
                "page_no": item.get("page_no"),
                "quote": str(item.get("content") or "")[:300],
                "score": item.get("score"),
            }
            for item in search_items
        ]
        profile_data = profile.model_dump(mode="json") if hasattr(profile, "model_dump") else dict(profile)
        return {
            "topic": topic,
            "modality": modality,
            "requirement": requirement or "",
            "profile": profile_data,
            "citations": citations,
            "source_summary": "\n".join(f"[{i + 1}] {c['quote']}" for i, c in enumerate(citations[:6])),
            "style_hint": self._style_hint(profile_data),
        }

    def _style_hint(self, profile: dict[str, Any]) -> str:
        text = str(profile)
        if "图" in text or "可视" in text or "动画" in text:
            return "使用图解、步骤化、低认知负担的教学视觉风格"
        if "代码" in text:
            return "结合代码变量、执行过程和调试视角"
        return "使用清晰、简洁、适合大学课程的教学风格"
