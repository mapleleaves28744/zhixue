from __future__ import annotations

from uuid import UUID

from arq.connections import RedisSettings

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.repositories.agent_task_repository import AgentTaskRepository
from app.services.agent_queue_service import AgentQueueService
from app.services.agent_runtime_service import AgentRuntimeService
from app.workers.multimodal_worker import run_multimodal_video_job


async def recover_orphaned_agent_tasks(ctx: dict) -> None:
    async with AsyncSessionLocal() as db:
        tasks = await AgentTaskRepository(db).list_orphaned_queued_tasks(limit=50)
        if not tasks:
            return
        recovered = await AgentQueueService().recover_orphaned_tasks([task.id for task in tasks])
        if recovered:
            print(f"Recovered {recovered} orphaned queued agent task(s)")


async def run_agent_task_job(ctx: dict, task_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        return await AgentRuntimeService(db).execute(UUID(task_id))


async def resume_agent_task_job(ctx: dict, task_id: str, approved: bool) -> dict:
    async with AsyncSessionLocal() as db:
        return await AgentRuntimeService(db).execute(UUID(task_id), approved=approved)


class WorkerSettings:
    functions = [run_agent_task_job, resume_agent_task_job, run_multimodal_video_job]
    on_startup = recover_orphaned_agent_tasks
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = settings.agent_worker_concurrency
    job_timeout = 1800
    keep_result = 3600
