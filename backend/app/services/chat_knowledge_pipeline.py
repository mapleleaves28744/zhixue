"""对话完成后的知识图谱沉淀与 EventBus 通知。"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

logger = logging.getLogger(__name__)


async def extract_knowledge_from_dialogue(
    db: AsyncSession,
    *,
    current_user: User,
    course_id: UUID,
    question: str,
    answer: str,
) -> dict[str, Any]:
    dialogue_text = f"问：{question.strip()}\n答：{answer.strip()}".strip()
    if len(dialogue_text) < 4:
        return {
            "entities_merged": 0,
            "relations_merged": 0,
            "created_entities": 0,
            "created_relations": 0,
            "wiki_pages_touched": 0,
        }

    from app.services.knowledge_graph_service import KnowledgeGraphService

    return await KnowledgeGraphService(db).extract_from_dialogue_text(
        current_user=current_user,
        course_id=course_id,
        dialogue_text=dialogue_text,
    )


async def publish_chat_completed(
    *,
    user_id: UUID,
    course_id: UUID,
    question: str,
    answer: str,
    citations: list[dict[str, Any]] | None = None,
    knowledge_id: UUID | None = None,
    message_id: str | None = None,
    extract_result: dict[str, Any] | None = None,
    source: str = "chat_pipeline",
) -> bool:
    try:
        from app.core.event_bus import get_event_bus

        await get_event_bus().publish(
            "chat_completed",
            {
                "user_id": user_id,
                "course_id": course_id,
                "knowledge_id": knowledge_id,
                "question": question,
                "answer": answer,
                "citations": citations or [],
                "message_id": message_id,
                "extract_result": extract_result or {},
                "skip_graph_extract": bool(extract_result),
            },
            source=source,
        )
        return True
    except Exception:
        logger.exception("chat_knowledge_pipeline: publish chat_completed failed")
        return False


def summarize_extract_for_ui(result: dict[str, Any] | None) -> dict[str, int]:
    data = result or {}
    return {
        "created_entities": int(data.get("created_entities") or 0),
        "created_relations": int(data.get("created_relations") or 0),
        "entities_merged": int(data.get("entities_merged") or 0),
        "wiki_pages_touched": int(data.get("wiki_pages_touched") or 0),
    }
