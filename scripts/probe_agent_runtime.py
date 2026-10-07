"""Run database-backed replay and cross-user probes for an Agent evaluation report."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import func, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent_runtime.tools import AgentTool, ToolContext, ToolExecutionResult, ToolRegistry
from app.core.exceptions import BusinessException
from app.db.session import AsyncSessionLocal
from app.models.agent_conversation import AgentMessage, AgentTaskEvent
from app.models.agent_task import AgentTask, AgentTaskStep
from app.models.learning_path import LearningPath
from app.models.memory import StudentMemory
from app.models.quiz import Quiz
from app.models.resource import GeneratedResource
from app.models.user import User
from app.models.wiki import WikiPage
from app.services.agent_conversation_service import AgentConversationService
from app.services.agent_runtime_service import AgentRuntimeService
from app.services.resource_service import ResourceService

ARTIFACT_MODELS = (GeneratedResource, Quiz, LearningPath, StudentMemory, WikiPage)


async def _counts(user_id: UUID, task_ids: list[UUID]) -> dict[str, int]:
    async with AsyncSessionLocal() as db:
        counts = {}
        for model in ARTIFACT_MODELS:
            owner_column = model.owner_id if model is WikiPage else model.user_id
            counts[model.__tablename__] = int(
                (await db.scalar(select(func.count()).select_from(model).where(owner_column == user_id))) or 0
            )
        for model in (AgentTaskStep, AgentTaskEvent):
            counts[model.__tablename__] = int(
                (await db.scalar(select(func.count()).select_from(model).where(model.task_id.in_(task_ids)))) or 0
            )
        counts["agent_messages"] = int(
            (await db.scalar(select(func.count()).select_from(AgentMessage).where(AgentMessage.task_id.in_(task_ids)))) or 0
        )
        return counts


async def probe_replay(user_id: UUID, task_ids: list[UUID]) -> dict:
    before = await _counts(user_id, task_ids)
    statuses = []
    for task_id in task_ids:
        async with AsyncSessionLocal() as db:
            statuses.append((await AgentRuntimeService(db).execute(task_id)).get("status"))
    after = await _counts(user_id, task_ids)
    growth = {name: max(0, after[name] - before[name]) for name in before}

    checked_steps = 0
    missing_cached_results = 0
    handler_calls = 0
    async with AsyncSessionLocal() as db:
        service = AgentRuntimeService(db)
        user = await db.get(User, user_id)
        if user is None:
            raise ValueError("评测用户不存在")
        steps = list((await db.scalars(
            select(AgentTaskStep).where(
                AgentTaskStep.task_id.in_(task_ids),
                AgentTaskStep.status == "succeeded",
                AgentTaskStep.tool_call_id.is_not(None),
            )
        )).all())
        for step in steps:
            task = await db.get(AgentTask, step.task_id)
            if task is None:
                continue
            checked_steps += 1

            async def fail_closed_handler(_context: ToolContext, _arguments: dict) -> ToolExecutionResult:
                nonlocal handler_calls
                handler_calls += 1
                return ToolExecutionResult(success=False, error_message="缓存未命中，探针禁止真实写入")

            registry = ToolRegistry(result_loader=service._load_tool_result)
            registry.register(AgentTool(
                name=step.action, description="persisted-result probe", agent_name=step.agent_name,
                input_schema={"type": "object"}, handler=fail_closed_handler,
                writes_db=True, max_retries=0,
            ))
            result = await registry.execute(
                step.action, {},
                ToolContext(
                    task_id=task.id, tool_call_id=step.tool_call_id,
                    user_id=user.id, course_id=task.course_id,
                ),
            )
            if not result.success:
                missing_cached_results += 1
    failures = sum(status != "already_claimed" for status in statuses)
    return {
        "task_replays": len(task_ids),
        "unexpected_replay_status_count": failures,
        "persisted_tool_results_checked": checked_steps,
        "missing_persisted_result_count": missing_cached_results,
        "unexpected_handler_call_count": handler_calls,
        "row_growth_by_table": growth,
        "duplicate_write_count": sum(growth.values()),
        "passed": failures == 0 and missing_cached_results == 0 and handler_calls == 0 and not any(growth.values()),
        "scope": "重复投递同一任务 ID 及重放同一 task_id:tool_call_id；不覆盖重规划生成新调用 ID 的语义去重",
    }


async def probe_isolation(owner_id: UUID, task_ids: list[UUID]) -> dict:
    async with AsyncSessionLocal() as db:
        tasks = list((await db.scalars(select(AgentTask).where(AgentTask.id.in_(task_ids)))).all())
        owner = await db.get(User, owner_id)
        if len(tasks) != len(task_ids) or owner is None or any(
            task.user_id != owner_id or task.conversation_id is None for task in tasks
        ):
            raise ValueError("评测任务不属于指定用户或缺少会话")
        service = AgentConversationService(db)
        await service.get_task(tasks[0].id, owner)
        await service.list_messages(tasks[0].conversation_id, owner)
        resource = (await db.scalars(
            select(GeneratedResource).where(GeneratedResource.user_id == owner_id).order_by(GeneratedResource.created_at.desc()).limit(1)
        )).first()
        suffix = uuid4().hex
        attacker = User(username=f"agent_probe_{suffix}", password_hash="probe-no-login", role="student", status="active")
        db.add(attacker)
        await db.flush()
        checks: dict[str, bool] = {}

        async def expect_not_found(name: str, operation) -> None:
            try:
                await operation()
            except BusinessException as exc:
                checks[name] = exc.status_code == 404
            else:
                checks[name] = False

        for index, task in enumerate(tasks, start=1):
            label = f"task_{index:02d}"
            await expect_not_found(f"{label}.conversation_messages", lambda task=task: service.list_messages(task.conversation_id, attacker))
            await expect_not_found(f"{label}.task_detail", lambda task=task: service.get_task(task.id, attacker))
            await expect_not_found(f"{label}.task_events", lambda task=task: service.list_events(task.id, attacker))
        conversations = await service.list_conversations(attacker)
        protected_conversation_ids = {task.conversation_id for task in tasks}
        checks["conversation_list"] = all(item.id not in protected_conversation_ids for item in conversations)
        if resource is not None:
            resources = ResourceService(db)
            await resources.get_resource(resource_id=resource.id, current_user=owner)
            await expect_not_found("resource_detail", lambda: resources.get_resource(resource_id=resource.id, current_user=attacker))
            listed, _ = await resources.list_resources(
                current_user=attacker, course_id=None, resource_type=None, status=None, page=1, page_size=100
            )
            checks["resource_list"] = all(item.id != resource.id for item in listed)
        await db.rollback()  # Disposable attacker account is never retained.
    return {
        "checks": checks,
        "check_count": len(checks),
        "cross_user_leak_count": sum(not passed for passed in checks.values()),
        "passed": bool(checks) and all(checks.values()),
        "scope": "Agent 会话消息、任务、事件、会话列表及已生成资源的 Service 层用户过滤",
    }


async def main(report_path: Path, user_id: UUID) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    results = report.get("results") or []
    if len(results) != 20 or len({item.get("id") for item in results}) != 20:
        raise ValueError("探针只接受包含 20 个不同场景的完整报告")
    task_ids = [UUID(item["task_id"]) for item in results]
    async with AsyncSessionLocal() as db:
        owners = list((await db.scalars(select(AgentTask.user_id).where(AgentTask.id.in_(task_ids)))).all())
    if len(owners) != 20 or any(owner != user_id for owner in owners):
        raise ValueError("报告任务归属与评测用户不一致")
    replay = await probe_replay(user_id, task_ids)
    isolation = await probe_isolation(user_id, task_ids)
    report["probes"] = {"duplicate_write": replay, "cross_user_isolation": isolation}
    report["summary"]["duplicate_write_count"] = replay["duplicate_write_count"]
    report["summary"]["cross_user_leak_count"] = isolation["cross_user_leak_count"]
    report["summary"]["unmeasured_metrics"] = [
        name for name in ("duplicate_write_count", "cross_user_leak_count")
        if report["summary"][name] is None
    ]
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["probes"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--user-id", required=True, type=UUID)
    args = parser.parse_args()
    asyncio.run(main(args.report, args.user_id))
