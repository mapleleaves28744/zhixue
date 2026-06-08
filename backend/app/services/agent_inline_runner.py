from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.repositories.agent_task_repository import AgentTaskRepository
from app.services.agent_runtime_service import AgentRuntimeService


logger = logging.getLogger(__name__)


def schedule_inline_fallback(task_id: UUID, *, delay_seconds: float | None = None) -> None:
    """When ARQ worker is not running, queued tasks would stall forever."""
    if not settings.agent_inline_fallback:
        return
    delay = delay_seconds if delay_seconds is not None else settings.agent_inline_fallback_delay_seconds
    asyncio.create_task(_run_inline_fallback(task_id, delay))


async def _run_inline_fallback(task_id: UUID, delay_seconds: float) -> None:
    await asyncio.sleep(delay_seconds)
    async with AsyncSessionLocal() as db:
        task = await AgentTaskRepository(db).get_by_id(task_id)
        if task is None or task.status != "queued" or task.started_at is not None:
            return
        logger.warning(
            "Agent task %s still queued after %.1fs; executing inline fallback",
            task_id,
            delay_seconds,
        )
        try:
            await AgentRuntimeService(db).execute(task_id)
        except Exception:
            logger.exception("Inline agent fallback failed for task %s", task_id)
