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
    """答题提交 → 触发记忆反思（轻量级，不阻塞）。"""
    user_id = event.data.get("user_id")
    course_id = event.data.get("course_id")
    if not user_id:
        return

    logger.debug("EventBus: quiz_submit for user=%s, triggering memory reflect", user_id)

    try:
        from app.db.session import AsyncSessionLocal
        from app.services.memory_service import MemoryService

        async with AsyncSessionLocal() as db:
            await MemoryService(db).reflect(
                user_id=user_id,
                course_id=course_id,
            )
            await db.commit()
    except Exception:
        logger.exception("EventBus: memory reflect failed after quiz_submit")


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
    logger.info("EventBus: default handlers registered")
