import asyncio

from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.services.agent_queue_service import AgentQueueService


async def main() -> None:
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT id FROM agent_tasks "
                    "WHERE status = 'queued' AND started_at IS NULL AND runtime_mode = 'langgraph' "
                    "ORDER BY created_at ASC LIMIT 50"
                )
            )
        ).all()
        task_ids = [row.id for row in rows]
        print("orphaned", len(task_ids), [str(item) for item in task_ids])
    if not task_ids:
        return
    recovered = await AgentQueueService().recover_orphaned_tasks(task_ids)
    print("recovered", recovered)


asyncio.run(main())
