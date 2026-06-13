from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from arq.connections import RedisSettings

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.repositories.agent_conversation_repository import AgentConversationRepository
from app.repositories.agent_task_repository import AgentTaskRepository
from app.services.agent_queue_service import AgentQueueService
from app.services.agent_runtime_service import AgentRuntimeService
from app.workers.multimodal_worker import run_multimodal_video_job
from app.workers.immersive_classroom_worker import run_immersive_classroom_job
from app.workers.classroom_video_export_worker import run_classroom_video_export_job


async def recover_orphaned_agent_tasks(ctx: dict) -> None:
    async with AsyncSessionLocal() as db:
        task_repo = AgentTaskRepository(db)
        conversation_repo = AgentConversationRepository(db)
        stale_cutoff = datetime.now(UTC) - timedelta(minutes=30)
        stale_tasks = await task_repo.list_stale_running_tasks(older_than=stale_cutoff, limit=50)
        for task in stale_tasks:
            message = "Agent 任务长时间无进展，Worker 启动时已自动结束。请重新发起或查看已生成产物。"
            await task_repo.update_task(
                task,
                status="failed",
                error_message=message,
                finished_at=datetime.now(UTC),
            )
            await conversation_repo.add_event(
                task_id=task.id,
                conversation_id=task.conversation_id,
                event_type="failed",
                payload={"status": "failed", "error_message": message},
            )
        if stale_tasks:
            await db.commit()
            print(f"Marked {len(stale_tasks)} stale running agent task(s) as failed")

        tasks = await task_repo.list_orphaned_queued_tasks(limit=50)
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
    functions = [
        run_agent_task_job,
        resume_agent_task_job,
        run_multimodal_video_job,
        run_immersive_classroom_job,
        run_classroom_video_export_job,
    ]
    on_startup = recover_orphaned_agent_tasks
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = settings.agent_worker_concurrency
    job_timeout = 1800
    keep_result = 3600
