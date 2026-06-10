"""对话完成 → 异步抽取个人知识图谱。"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.core.event_bus import Event

logger = logging.getLogger(__name__)


async def handle_chat_completed(event: Event) -> None:
    user_id = event.data.get("user_id")
    course_id = event.data.get("course_id")
    if not user_id or not course_id:
        return

    question = str(event.data.get("question") or "")
    answer = str(event.data.get("answer") or "")
    dialogue_text = f"问：{question}\n答：{answer}".strip()
    if len(dialogue_text) < 4:
        return

    logger.info("KnowledgeExtract: chat_completed user=%s course=%s", user_id, course_id)

    try:
        from sqlalchemy import select

        from app.db.session import AsyncSessionLocal
        from app.models.user import User
        from app.services.knowledge_graph_service import KnowledgeGraphService

        async with AsyncSessionLocal() as db:
            user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            if user is None:
                return
            result = await KnowledgeGraphService(db).extract_from_dialogue_text(
                current_user=user,
                course_id=UUID(str(course_id)),
                dialogue_text=dialogue_text,
            )
            await db.commit()
            event.data["_extract_result"] = result
            logger.info("KnowledgeExtract: merged %s", result)
    except Exception:
        logger.exception("KnowledgeExtract: failed for chat_completed")


async def handle_agent_task_completed(event: Event) -> None:
    if event.data.get("task_type") not in {"course_qa", "tutor_chat", "course_qa_stream"}:
        return
    await handle_chat_completed(event)
