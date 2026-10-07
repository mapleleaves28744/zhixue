"""PostgreSQL memory job faults with deterministic injected extraction, no LLM calls."""
import asyncio
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.course import Course
from app.models.memory import MemoryReflectionJob, StudentMemory
from app.services.learning_record_service import LearningRecordService
from app.services.memory_reflection_service import MemoryReflectionService
from evaluate_context_quality import BASE, append

KINDS = ("late_commit", "same_timestamp_100", "two_workers", "stale_lease_fence", "process_exit_after_claim", "empty_fake_evidence", "forget_during_extract")


async def extract(self, user_id, records):
    return [{"memory_type": "preference", "content": "学生喜欢用图解释", "evidence": [str(record.id)], "confidence": 0.8} for record in records]


async def run_batch(owner, course):
    async with AsyncSessionLocal() as db:
        return await MemoryReflectionService(db).process_next_batch(user_id=owner, course_id=course, include_recent=True)


async def crash_child(data):
    async def crash(*args, **kwargs):
        os._exit(74)
    with patch("app.agents.memory_agent.MemoryAgent.extract_candidates", crash):
        await run_batch(UUID(data["owner"]), UUID(data["course"]))


async def main(release: bool = False):
    owner = UUID(json.loads((BASE / "memory-fixtures.json").read_text(encoding="utf-8"))["owner_id"])
    output = BASE / ("memory-fault-release-results.jsonl" if release else "memory-fault-results.jsonl")
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()] if output.exists() else []
    done = {row["id"] for row in rows}
    for kind in KINDS:
        for index in range(6):
            identity = f"{kind}-{index}"
            if identity in done:
                continue
            row = {"id": identity, "kind": kind, "passed": False}
            try:
                async with AsyncSessionLocal() as db:
                    course = Course(owner_id=owner, title=f"记忆故障验收 {identity}", visibility="private", status="active")
                    db.add(course)
                    await db.flush()
                    source_count = 100 if kind == "same_timestamp_100" else 6 if kind == "two_workers" else 1
                    same_time = datetime.now(UTC)
                    for source_index in range(source_count):
                        record = await LearningRecordService(db).record_event(user_id=owner, course_id=course.id, event_type="chat",
                            event_source="synthetic_memory_fault", event_payload={"question": "我喜欢用图解释", "index": source_index}, commit=False)
                        record.created_at = same_time
                    await db.commit()
                    course_id = course.id
                    await MemoryReflectionService(db).discover_missing(user_id=owner, course_id=course_id)
                with patch("app.agents.memory_agent.MemoryAgent.extract_candidates", extract):
                    if kind == "forget_during_extract":
                        from app.services.memory_service import MemoryService
                        await run_batch(owner, course_id)
                        async with AsyncSessionLocal() as db:
                            old = (await db.execute(select(StudentMemory).where(StudentMemory.course_id == course_id))).scalar_one()
                            memory_id = old.id
                            await LearningRecordService(db).record_event(user_id=owner, course_id=course_id, event_type="chat",
                                event_source="synthetic_memory_fault", event_payload={"question": "我喜欢用图解释"}, commit=False)
                            await db.commit()
                            await MemoryReflectionService(db).discover_missing(user_id=owner, course_id=course_id)
                        async def forget(self, user_id, records):
                            # Keep an old active identity-map object alive across the model wait.
                            cached = await self.db.get(StudentMemory, memory_id)
                            assert cached.status == "active"
                            async with AsyncSessionLocal() as foreground:
                                await MemoryService(foreground).delete_memory(memory_id, owner)
                            assert cached.status == "active"
                            return await extract(self, user_id, records)
                        with patch("app.agents.memory_agent.MemoryAgent.extract_candidates", forget):
                            await run_batch(owner, course_id)
                        source_count = 2
                    elif kind == "late_commit":
                        await run_batch(owner, course_id)
                        async with AsyncSessionLocal() as db:
                            late = await LearningRecordService(db).record_event(user_id=owner, course_id=course_id, event_type="chat",
                                event_source="synthetic_memory_fault", event_payload={"question": "我喜欢用图解释"}, commit=False)
                            late.created_at = same_time - timedelta(days=1)
                            await db.commit()
                            await MemoryReflectionService(db).discover_missing(user_id=owner, course_id=course_id)
                        await run_batch(owner, course_id)
                        source_count = 2
                    elif kind == "two_workers":
                        counts = await asyncio.gather(run_batch(owner, course_id), run_batch(owner, course_id))
                        assert sum(item["jobs"] for item in counts) == source_count
                    elif kind == "stale_lease_fence":
                        async def fence(self, user_id, records):
                            async with AsyncSessionLocal() as db:
                                job = (await db.execute(select(MemoryReflectionJob).where(MemoryReflectionJob.course_id == course_id))).scalar_one()
                                job.lease_owner = "new-evaluation-owner"
                                job.lease_version += 1
                                job.lease_until = datetime.now(UTC) - timedelta(seconds=1)
                                await db.commit()
                            return await extract(self, user_id, records)
                        with patch("app.agents.memory_agent.MemoryAgent.extract_candidates", fence):
                            stale = await run_batch(owner, course_id)
                        assert stale["jobs"] == 0
                        recovered = await run_batch(owner, course_id)
                        assert recovered["jobs"] == 1
                    elif kind == "process_exit_after_claim":
                        path = BASE / f"memory-process-{uuid4().hex[:8]}.json"
                        path.write_text(json.dumps({"owner": str(owner), "course": str(course_id)}), encoding="utf-8")
                        process = await asyncio.to_thread(subprocess.run,
                            [sys.executable, str(Path(__file__).resolve()), "--crash", str(path)], cwd=str(ROOT / "backend"),
                            capture_output=True, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                        assert process.returncode == 74
                        async with AsyncSessionLocal() as db:
                            job = (await db.execute(select(MemoryReflectionJob).where(MemoryReflectionJob.course_id == course_id))).scalar_one()
                            assert job.status == "running"
                            job.lease_until = datetime.now(UTC) - timedelta(seconds=1)
                            await db.commit()
                        await run_batch(owner, course_id)
                    elif kind == "empty_fake_evidence":
                        async def invalid(self, user_id, records):
                            return [] if index % 2 else [{"memory_type": "preference", "content": "学生喜欢用图解释", "evidence": [str(uuid4())], "confidence": 0.9}]
                        with patch("app.agents.memory_agent.MemoryAgent.extract_candidates", invalid):
                            await run_batch(owner, course_id)
                    else:
                        for _ in range(5):
                            if not (await run_batch(owner, course_id))["jobs"]:
                                break
                    assert (await run_batch(owner, course_id))["jobs"] == 0
                async with AsyncSessionLocal() as db:
                    jobs = list((await db.execute(select(MemoryReflectionJob).where(MemoryReflectionJob.course_id == course_id))).scalars().all())
                    assert len(jobs) == source_count
                    assert all(job.status in {"succeeded", "succeeded_no_output"} for job in jobs)
                    memories = list((await db.execute(select(StudentMemory).where(StudentMemory.course_id == course_id))).scalars().all())
                    if kind == "empty_fake_evidence":
                        assert not memories
                    elif kind == "forget_during_extract":
                        assert len(memories) == 1 and memories[0].status == "forgotten" and memories[0].reinforcement_count == 1
                    else:
                        assert len(memories) == 1 and memories[0].reinforcement_count == source_count
                    row["processed_sources"] = len(jobs)
                row["passed"] = True
            except Exception as exc:
                row.update(error_type=type(exc).__name__, detail=str(exc)[:240])
            append(output, row)
            rows.append(row)
            print(identity, "PASS" if row["passed"] else "FAIL", flush=True)
    report = {"scope": "real PostgreSQL faults, deterministic injected extraction; not real LLM quality",
        "total": len(rows), "passed": sum(row["passed"] for row in rows),
        "groups": {kind: {"total": sum(row["kind"] == kind for row in rows), "passed": sum(row["passed"] for row in rows if row["kind"] == kind)} for kind in KINDS}}
    report["evaluation_status"] = "post-fix regression" if release else "initial fault evaluation"
    report_path = BASE / ("memory-fault-release-report.json" if release else "memory-fault-report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)
    if report["passed"] != report["total"]:
        raise SystemExit(1)

if __name__ == "__main__":
    if sys.platform == "win32": asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(crash_child(json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))) if "--crash" in sys.argv else main(release="--release" in sys.argv))
