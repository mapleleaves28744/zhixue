from __future__ import annotations

from uuid import UUID

from arq.connections import RedisSettings

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services.agent_runtime_service import AgentRuntimeService


async def run_agent_task_job(ctx: dict, task_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        return await AgentRuntimeService(db).execute(UUID(task_id))


async def resume_agent_task_job(ctx: dict, task_id: str, approved: bool) -> dict:
    async with AsyncSessionLocal() as db:
        return await AgentRuntimeService(db).execute(UUID(task_id), approved=approved)


class WorkerSettings:
    functions = [run_agent_task_job, resume_agent_task_job]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = settings.agent_worker_concurrency
    job_timeout = 1800
    keep_result = 3600
