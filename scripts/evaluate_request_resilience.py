"""Real PostgreSQL service concurrency and process recovery; no LLM throughput claim."""
from __future__ import annotations
import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.course import Course
from app.models.tutor_request import TutorRequest
from app.models.agent_task import AgentTask
from app.repositories.agent_conversation_repository import AgentConversationRepository
from app.services.tutor_request_service import TutorRequestService, TutorClaim
from app.schemas.tutor import TutorChatRequest, TutorChatResponse
from app.core.exceptions import BusinessException

OUTPUT = ROOT / "data/seed_knowledge/data_structure/eval/quality_v1/resilience-report.json"


async def child(mode: str, path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if mode == "recover":
        from app.workers.agent_worker import recover_orphaned_agent_tasks
        await recover_orphaned_agent_tasks({"recovery_user_id": data["owner"]})
        return
    async with AsyncSessionLocal() as db:
        payload = TutorChatRequest.model_validate(data["payload"])
        claim = await TutorRequestService(db).claim(payload, UUID(data["owner"]))
        data["claim"] = {"request_id": str(claim.request_id), "owner": claim.owner, "version": claim.version}
        if mode == "commit-crash":
            repository = AgentConversationRepository(db)
            conversation = await repository.get_for_user(payload.conversation_id, UUID(data["owner"]))
            await repository.add_message(conversation=conversation,
                user_id=UUID(data["owner"]), role="assistant", message_type="tutor",
                content="persisted-before-disconnect", client_request_id=payload.client_request_id,
                payload=TutorChatResponse(answer="persisted-before-disconnect").model_dump(mode="json"))
            await db.commit()
        path.write_text(json.dumps(data), encoding="utf-8")
    os._exit(73)  # Only the evaluation subprocess exits; no shared worker is killed.


async def run_child(mode: str, data: dict):
    path = OUTPUT.with_name(f"process-{uuid4().hex[:8]}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    # asyncpg needs the Selector loop on Windows, which cannot create subprocesses.
    # The blocking child wait runs in a thread, leaving the event loop responsive.
    process = await asyncio.to_thread(subprocess.run,
        [sys.executable, str(Path(__file__).resolve()), mode, str(path)],
        cwd=str(ROOT / "backend"), capture_output=True, timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    stderr = process.stderr
    expected = 0 if mode == "recover" else 73
    if process.returncode != expected:
        raise RuntimeError(f"Evaluation subprocess failed: {process.returncode}: {stderr.decode(errors='replace')[-600:]}")
    return json.loads(path.read_text(encoding="utf-8"))


async def main():
    if OUTPUT.exists():
        import shutil
        shutil.copy2(OUTPUT, OUTPUT.with_name(f"resilience-previous-{uuid4().hex[:8]}.json"))
    report = {"started_at": datetime.now(UTC).isoformat(), "scope": "PostgreSQL Service calls; no HTTP/LLM throughput or whole-system chaos claim", "checks": [], "load": []}
    async with AsyncSessionLocal() as db:
        owner = User(username=f"context_eval_resilience_{uuid4().hex[:8]}", password_hash="disabled-evaluation-account", status="disabled")
        db.add(owner)
        await db.flush()
        course = Course(owner_id=owner.id, title="合成恢复验收", visibility="private", status="active")
        db.add(course)
        await db.flush()
        conversation = await AgentConversationRepository(db).create(user_id=owner.id, course_id=course.id)
        await db.commit()
        owner_id, course_id, conversation_id = owner.id, course.id, conversation.id
    report["owner_id"] = str(owner_id)
    def request():
        return TutorChatRequest(course_id=course_id, conversation_id=conversation_id, client_request_id=uuid4(), question="验收请求")
    async def roundtrip(payload):
        async with AsyncSessionLocal() as db:
            service = TutorRequestService(db)
            claim = await service.claim(payload, owner_id)
            await service.complete(claim, TutorChatResponse(answer="deterministic-evaluation"))
            replay = await service.claim(payload, owner_id)
            assert replay.completed.answer == "deterministic-evaluation"
    for concurrency in (1, 5, 10):
        semaphore = asyncio.Semaphore(concurrency)
        async def execute():
            async with semaphore:
                try:
                    await roundtrip(request())
                    return True
                except Exception as exc:
                    return type(exc).__name__
        started = time.monotonic()
        outcomes = await asyncio.gather(*(execute() for _ in range(100)))
        report["load"].append({"concurrency": concurrency, "requests": 100, "passed": sum(value is True for value in outcomes),
                               "seconds": round(time.monotonic() - started, 3), "errors": [value for value in outcomes if value is not True]})
        print("load", report["load"][-1], flush=True)
    async def check(name, operation):
        item = {"name": name, "passed": False}
        try:
            await operation()
            item["passed"] = True
        except Exception as exc:
            item["error_type"] = type(exc).__name__
            item["detail"] = str(exc)[:240]
        report["checks"].append(item)
        print(name, "PASS" if item["passed"] else "FAIL", flush=True)
    async def duplicate():
        payload = request()
        async def acquire():
            async with AsyncSessionLocal() as db:
                try:
                    return await TutorRequestService(db).claim(payload, owner_id)
                except BusinessException as exc:
                    assert exc.status_code == 409
                    return None
        claims = await asyncio.gather(*(acquire() for _ in range(10)))
        assert sum(claim is not None for claim in claims) == 1
    await check("ten_simultaneous_duplicates_one_owner", duplicate)
    async def restart():
        payload = request()
        data = await run_child("claim-crash", {"owner": str(owner_id), "payload": payload.model_dump(mode="json")})
        old = TutorClaim(UUID(data["claim"]["request_id"]), data["claim"]["owner"], data["claim"]["version"])
        async with AsyncSessionLocal() as db:
            row = await db.get(TutorRequest, old.request_id)
            assert row.status == "running"
            row.lease_until = datetime.now(UTC) - timedelta(seconds=1)  # Accelerated lease expiry, not an actual 5-minute wait.
            await db.commit()
            service = TutorRequestService(db)
            new = await service.claim(payload, owner_id)
            assert new.version > old.version
            try:
                await service.complete(old, TutorChatResponse(answer="stale"))
                raise AssertionError("Stale owner committed")
            except BusinessException as exc:
                assert exc.status_code == 409
            await db.rollback()
            await service.complete(new, TutorChatResponse(answer="recovered"))
    await check("process_exit_lease_reclaim_stale_owner_fenced", restart)
    async def disconnect():
        payload = request()
        await run_child("commit-crash", {"owner": str(owner_id), "payload": payload.model_dump(mode="json")})
        async with AsyncSessionLocal() as db:
            service = TutorRequestService(db)
            status = await service.status(conversation_id=conversation_id, client_request_id=payload.client_request_id, user_id=owner_id)
            assert status["status"] == "succeeded"
            assert status["response"]["answer"] == "persisted-before-disconnect"
            assert (await service.claim(payload, owner_id)).completed.answer == "persisted-before-disconnect"
    await check("response_committed_then_process_exit_recovered", disconnect)
    async def failed_retry():
        payload = request()
        async with AsyncSessionLocal() as db:
            service = TutorRequestService(db)
            first = await service.claim(payload, owner_id)
            await service.fail(first, TimeoutError("simulated transport failure"))
            second = await service.claim(payload, owner_id)
            assert second.version > first.version
            await service.complete(second, TutorChatResponse(answer="retried"))
    await check("failed_request_can_retry", failed_retry)
    async def cached_lease():
        payload = request()
        async with AsyncSessionLocal() as first_db:
            first_service = TutorRequestService(first_db)
            old_claim = await first_service.claim(payload, owner_id)
            cached = await first_db.get(TutorRequest, old_claim.request_id)
            async with AsyncSessionLocal() as other_db:
                newer = await other_db.get(TutorRequest, old_claim.request_id)
                newer.lease_until = datetime.now(UTC) - timedelta(seconds=1)
                await other_db.commit()
                new_service = TutorRequestService(other_db)
                new_claim = await new_service.claim(payload, owner_id)
                await new_service.complete(new_claim, TutorChatResponse(answer="same-answer"))
            assert cached.lease_version == old_claim.version
            try:
                await first_service.complete(old_claim, TutorChatResponse(answer="same-answer"))
                raise AssertionError("Cached old owner modified a completed request")
            except BusinessException as exc:
                assert exc.status_code == 409
            await first_db.rollback()
            status = await first_service.status(conversation_id=conversation_id, client_request_id=payload.client_request_id, user_id=owner_id)
            assert status["status"] == "succeeded" and status["response"]["answer"] == "same-answer"
    await check("cached_request_cannot_override_new_owner_completed_result", cached_lease)
    async def worker_restart():
        async with AsyncSessionLocal() as db:
            task = AgentTask(user_id=owner_id, course_id=course_id, conversation_id=conversation_id,
                task_goal="合成恢复任务", task_type="evaluation", status="running", runtime_mode="langgraph",
                started_at=datetime.now(UTC) - timedelta(hours=1), last_event_at=datetime.now(UTC) - timedelta(hours=1))
            db.add(task)
            await db.commit()
            task_id = task.id
        await run_child("recover", {"owner": str(owner_id)})
        async with AsyncSessionLocal() as db:
            task = await db.get(AgentTask, task_id)
            assert task.status == "failed" and task.finished_at is not None
    await check("new_process_runs_scoped_worker_startup_recovery", worker_restart)
    report["passed"] = all(item["passed"] for item in report["checks"]) and all(item["passed"] == 100 for item in report["load"])
    report["finished_at"] = datetime.now(UTC).isoformat()
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    if sys.platform == "win32": asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(child(sys.argv[1], Path(sys.argv[2])) if len(sys.argv) > 1 else main())
