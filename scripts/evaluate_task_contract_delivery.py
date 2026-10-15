"""Real Provider probes for independent deliverables, revisions and source identity."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.agent_task import AgentTask, AgentTaskStep
from app.models.agent_conversation import AgentMessage
from app.models.resource import GeneratedResource
from app.models.user import User
from app.schemas.agent_conversation import AgentConversationCreateRequest, AgentMessageCreateRequest
from app.services.agent_conversation_service import AgentConversationService
from sqlalchemy import select


async def wait_task(task_id: UUID, timeout_seconds: int) -> tuple[dict, list[str]]:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        async with AsyncSessionLocal() as db:
            task = await db.get(AgentTask, task_id)
            if task.status in {"succeeded", "failed", "cancelled", "waiting_confirmation"}:
                assert task.status == "succeeded", f"{task.status}: {task.error_message}"
                steps = list((await db.scalars(select(AgentTaskStep).where(AgentTaskStep.task_id == task_id))).all())
                assert not any(step.status == "running" for step in steps)
                frame = (task.input_payload or {})["intent_frame_v1"]
                assert frame["parser"] == "semantic_v1"
                assert (task.plan_json or {}).get("intent_frame_v1") == frame, "Displayed contract differs from executed contract"
                assert all(item["status"] == "succeeded" for item in (task.plan_json or {}).get("subtask_progress_v1", [])), "Incomplete subtask"
                refs = (task.plan_json or {}).get("artifact_refs", [])
                ids = [UUID(str(ref["id"])) for ref in refs if ref.get("type") == "resource"]
                resources = list((await db.scalars(select(GeneratedResource).where(GeneratedResource.id.in_(ids)))).all())
                assert len(resources) == len(ids) and ids, "Missing persisted deliverables"
                assert all(item.user_id == task.user_id and item.course_id == task.course_id for item in resources)
                assert all(item.model_name == settings.llm_model_name for item in resources), "Deliverable used Mock or a different model"
                message = await db.scalar(select(AgentMessage).where(AgentMessage.task_id == task_id, AgentMessage.role == "assistant"))
                assert message and all(item.title in message.content for item in resources), "Final answer omits generated resources"
                assert all(item.content.strip() for item in resources), "Missing resource content"
                return frame, [item.title for item in resources]
        await asyncio.sleep(0.5)
    raise TimeoutError(f"Contract delivery exceeded {timeout_seconds} seconds")


async def evaluate(args) -> bool:
    report = {"model": settings.llm_model_name, "started_at": datetime.now(UTC).isoformat(), "passed": False}
    try:
        assert settings.llm_provider != "mock" and settings.llm_api_key
        async with AsyncSessionLocal() as db:
            user = await db.get(User, args.user_id)
            assert user.username.startswith("context_eval_"), "Use an isolated evaluation account"
            service = AgentConversationService(db)
            conversation = await service.create_conversation(AgentConversationCreateRequest(course_id=args.course_id), user)
            payload = AgentMessageCreateRequest(content="栈和队列各生成一份简短讲解资源", client_request_id=uuid4())
            original = await service.send_message(conversation.id, payload, user)
            replay = await service.send_message(conversation.id, payload, user)
            assert replay.task.id == original.task.id
        report["original_task_id"] = str(original.task.id)
        frame, titles = await wait_task(original.task.id, args.timeout_seconds)
        assert sorted(item["topic"] for item in frame["tasks"]) == ["栈", "队列"]
        assert len(titles) == 2 and any("栈" in title and "队列" not in title for title in titles) and any("队列" in title and "栈" not in title for title in titles), "Topics were combined into one deliverable"
        async with AsyncSessionLocal() as db:
            user = await db.get(User, args.user_id)
            revised = await AgentConversationService(db).send_message(conversation.id,
                AgentMessageCreateRequest(content="改成归并排序的简短讲解，只生成一份资源", revises_task_id=original.task.id,
                                          client_request_id=uuid4()), user)
        report["revised_task_id"] = str(revised.task.id)
        revised_frame, revised_titles = await wait_task(revised.task.id, args.timeout_seconds)
        assert revised_frame["revision"] == frame["revision"] + 1
        assert len(revised_frame["tasks"]) == 1 and revised_frame["tasks"][0]["topic"] == "归并排序"
        assert revised_frame["tasks"][0]["source_message_id"] == str(original.message.id)
        assert len(revised_titles) == 1 and "归并" in revised_titles[0]
        report.update(passed=True, original_task_id=str(original.task.id), revised_task_id=str(revised.task.id),
                      checks=["request replay", "two distinct persisted resources", "revision has one new topic", "original source retained", "all subtask deliveries complete", "displayed contract matches execution", "final answer lists resources"],
                      original_titles=titles, revised_titles=revised_titles)
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        if isinstance(exc, TimeoutError):
            async with AsyncSessionLocal() as db:
                user = await db.get(User, args.user_id)
                task_id = report.get("revised_task_id") or report.get("original_task_id")
                if task_id:
                    await AgentConversationService(db).cancel_task(UUID(task_id), user)
                    report["timeout_cancelled"] = True
    report["finished_at"] = datetime.now(UTC).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return report["passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", type=UUID, required=True)
    parser.add_argument("--course-id", type=UUID, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=360)
    parser.add_argument("--output", type=Path, default=ROOT / "data/seed_knowledge/data_structure/eval/baselines/task_contract_delivery.json")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(0 if asyncio.run(evaluate(args)) else 1)
