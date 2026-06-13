"""默认事件处理器注册。

在 EventBus 启动时调用，注册系统级事件处理器。
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.event_bus import Event, get_event_bus

logger = logging.getLogger(__name__)


async def on_diagnosis_complete(event: Event) -> None:
    """诊断完成 → 触发自进化检测。"""
    if event.data.get("skip_auto_evolve"):
        return
    user_id = event.data.get("user_id")
    course_id = event.data.get("course_id")
    if not user_id or not course_id:
        return

    logger.info("EventBus: diagnosis_complete for user=%s, checking auto-evolve", user_id)

    try:
        from app.db.session import AsyncSessionLocal
        from app.services.evolution_service import EvolutionService

        async with AsyncSessionLocal() as db:
            await EvolutionService(db).auto_evolve_if_needed(
                user_id=user_id,
                course_id=course_id,
            )
            await db.commit()
    except Exception:
        logger.exception("EventBus: auto-evolve failed after diagnosis_complete")


async def on_quiz_submit(event: Event) -> None:
    """答题提交 → 记忆反思 + 掌握度更新。"""
    user_id = event.data.get("user_id")
    course_id = event.data.get("course_id")
    if not user_id:
        return

    logger.debug("EventBus: quiz_submit for user=%s", user_id)

    try:
        from uuid import UUID

        from app.db.session import AsyncSessionLocal
        from app.services.mastery_service import MasteryService
        from app.services.memory_service import MemoryService

        async with AsyncSessionLocal() as db:
            mastery = MasteryService(db)
            quiz_knowledge_id = event.data.get("quiz_knowledge_id")
            for item in event.data.get("answers") or []:
                kid = item.get("knowledge_id") or quiz_knowledge_id
                if not kid:
                    continue
                await mastery.apply_practice_update(
                    user_id=UUID(str(user_id)),
                    course_id=UUID(str(course_id)),
                    knowledge_id=UUID(str(kid)),
                    is_correct=bool(item.get("is_correct")),
                )
            if course_id:
                await mastery.sync_profile_snapshot(
                    user_id=UUID(str(user_id)),
                    course_id=UUID(str(course_id)),
                )
            await MemoryService(db).reflect(
                user_id=user_id,
                course_id=course_id,
            )
            await db.commit()
    except Exception:
        logger.exception("EventBus: quiz_submit handler failed")


async def on_chat_completed(event: Event) -> None:
    """对话完成 → 掌握度轻量更新 + 异步图谱抽取。"""
    user_id = event.data.get("user_id")
    course_id = event.data.get("course_id")
    knowledge_id = event.data.get("knowledge_id")
    if not user_id or not course_id:
        return

    try:
        from uuid import UUID

        from app.db.session import AsyncSessionLocal
        from app.services.mastery_service import MasteryService

        async with AsyncSessionLocal() as db:
            mastery = MasteryService(db)
            touched_ids = event.data.get("extract_result", {}).get("touched_knowledge_ids") or []
            for kid in touched_ids:
                await mastery.apply_ask_update(
                    user_id=UUID(str(user_id)),
                    course_id=UUID(str(course_id)),
                    knowledge_id=UUID(str(kid)),
                    understood=False,
                )
            if knowledge_id:
                await mastery.apply_ask_update(
                    user_id=UUID(str(user_id)),
                    course_id=UUID(str(course_id)),
                    knowledge_id=UUID(str(knowledge_id)),
                    understood=False,
                )
            if touched_ids or knowledge_id:
                await mastery.sync_profile_snapshot(
                    user_id=UUID(str(user_id)),
                    course_id=UUID(str(course_id)),
                )
                await db.commit()
    except Exception:
        logger.exception("EventBus: chat mastery update failed")

    try:
        from uuid import UUID

        from app.db.session import AsyncSessionLocal
        from app.services.profile_service import ProfileService

        question = str(event.data.get("question") or "").strip()
        answer = str(event.data.get("answer") or "").strip()
        if question and question not in {"你好", "您好", "hi", "hello"}:
            async with AsyncSessionLocal() as db:
                await ProfileService(db).ingest_dialogue_profile(
                    user_id=UUID(str(user_id)),
                    course_id=UUID(str(course_id)),
                    dialogue_text=f"学生问题：{question}\n回答摘要：{answer[:500]}",
                    source_message_id=str(event.data.get("message_id") or ""),
                )
    except Exception:
        logger.exception("EventBus: async course profile extraction failed")

    if event.data.get("skip_graph_extract"):
        return

    from app.workers.knowledge_extract_worker import handle_chat_completed

    await handle_chat_completed(event)


async def on_profile_update(event: Event) -> None:
    """画像更新 → 触发难度重新计算。"""
    user_id = event.data.get("user_id")
    course_id = event.data.get("course_id")
    accuracy = event.data.get("accuracy")
    weak_points = event.data.get("weak_points", [])
    if not user_id or not course_id:
        return

    logger.debug("EventBus: profile_update for user=%s, recalculating difficulty", user_id)

    try:
        from app.db.session import AsyncSessionLocal
        from app.services.difficulty_service import DifficultyService

        async with AsyncSessionLocal() as db:
            await DifficultyService(db).compute_and_update(
                user_id=user_id,
                course_id=course_id,
                accuracy=float(accuracy or 0),
                weak_points=weak_points,
            )
            await db.commit()
    except Exception:
        logger.exception("EventBus: difficulty adjustment failed after profile_update")


def register_default_handlers() -> None:
    """注册所有默认事件处理器。"""
    bus = get_event_bus()
    bus.subscribe("diagnosis_complete", on_diagnosis_complete)
    bus.subscribe("quiz_submit", on_quiz_submit)
    bus.subscribe("profile_update", on_profile_update)
    bus.subscribe("chat_completed", on_chat_completed)
    logger.info("EventBus: default handlers registered")
