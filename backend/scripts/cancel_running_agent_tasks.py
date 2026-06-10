"""Cancel all running/queued agent tasks for a user (emergency token saver)."""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.agent_task import AgentTask
from app.models.user import User


async def main() -> int:
    username = sys.argv[1] if len(sys.argv) > 1 else "student_demo"
    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if user is None:
            print(f"user not found: {username}", file=sys.stderr)
            return 1

        tasks = (
            await db.execute(
                select(AgentTask).where(
                    AgentTask.user_id == user.id,
                    AgentTask.status.in_(("running", "queued", "planned", "waiting_confirmation")),
                )
            )
        ).scalars().all()

        if not tasks:
            print("no running tasks")
            return 0

        for task in tasks:
            task.status = "cancelled"
            task.cancelled_at = datetime.now(UTC)
            task.error_message = "用户手动中止以节省 token"
            print(f"cancelled {task.id}: {str(task.task_goal or '')[:60]}")

        await db.commit()
        print(f"done: cancelled {len(tasks)} task(s)")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
