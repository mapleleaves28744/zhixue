"""Exercise lifecycle trajectories against local PostgreSQL, using an evaluation owner.

These are deterministic service integration cases, not model extraction accuracy scores.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.course import Course
from app.models.user import User
from app.models.memory import StudentMemoryEvent
from app.schemas.memory import MemoryUpdate
from app.services.learning_record_service import LearningRecordService
from app.services.memory_service import MemoryService
from app.services.memory_retrieval_service import MemoryRetrievalService


KINDS = ["forget_synonym", "source_dedup", "confirm_conflict", "archive", "correct",
         "expired", "course_overrides_global", "foreign_related", "scope_isolation", "evidence"]


async def evaluate(owner: UUID, output: Path):
    results = []
    async with AsyncSessionLocal() as db:
        user = await db.get(User, owner)
        assert user and user.username.startswith("context_eval_"), "Use the isolated evaluation account"
        for kind in KINDS:
            for index in range(6):
                result = {"id": f"{kind}_{index+1}", "passed": False}
                try:
                    course = Course(owner_id=owner, title=f"记忆验收 {kind} {index+1}", visibility="private", status="active")
                    db.add(course)
                    await db.flush()
                    service = MemoryService(db)
                    source = await LearningRecordService(db).record_event(user_id=owner, course_id=course.id,
                        event_type="feedback", event_source="context_evaluation", event_payload={"question": "我喜欢用图解释"}, commit=False)
                    async def upsert(content="学生喜欢用图解释", **kwargs):
                        return await service.upsert_memory(user_id=owner, course_id=course.id,
                            memory_type="preference", content=content, evidence=[str(source.id)], confidence=0.8, **kwargs)
                    old, action = await upsert()
                    assert action == "add"
                    await db.commit()
                    if kind == "forget_synonym":
                        await service.delete_memory(old.id, owner)
                        new, action = await upsert("学生希望通过示意图学习")
                        assert new.id == old.id and action == "skipped" and new.status == "forgotten"
                    elif kind == "source_dedup":
                        before = old.reinforcement_count
                        _, action = await upsert()
                        assert action == "skipped" and old.reinforcement_count == before
                    elif kind == "confirm_conflict":
                        old, _ = await upsert("学生喜欢详细讲解")
                        await db.commit()
                        new, action = await upsert("学生喜欢简短讲解")
                        assert action == "pending"
                        await db.commit()
                        await service.restore_memory(new.id, owner)
                        await db.refresh(old)
                        assert old.status == "superseded"
                    elif kind == "archive":
                        await service.update_memory(old.id, owner, MemoryUpdate(status="archived"))
                        new, action = await upsert()
                        assert action == "skipped" and new.status == "archived"
                    elif kind == "correct":
                        await service.update_memory(old.id, owner, MemoryUpdate(content="学生喜欢逐步讲解", confidence=0.6))
                        event = (await db.execute(select(StudentMemoryEvent).where(StudentMemoryEvent.memory_id == old.id,
                            StudentMemoryEvent.action == "correct"))).scalar_one()
                        assert event.before_snapshot["confidence"] == 0.8 and event.after_snapshot["confidence"] == 0.6
                    elif kind == "expired":
                        old.lifecycle_meta = {**old.lifecycle_meta, "valid_until": (datetime.now(UTC)-timedelta(days=1)).isoformat()}
                        await db.commit()
                        items = await MemoryRetrievalService(db).retrieve(user_id=owner, course_id=course.id, question="栈")
                        assert old.id not in {item.id for item in items}
                    elif kind == "course_overrides_global":
                        global_item, _ = await service.upsert_memory(user_id=owner, course_id=None, memory_type="preference",
                            content="学生喜欢用图解释", evidence=[str(source.id)], confidence=0.8)
                        await db.commit()
                        items = await MemoryRetrievalService(db).retrieve(user_id=owner, course_id=course.id, question="栈")
                        assert old.id in {item.id for item in items} and global_item.id not in {item.id for item in items}
                    elif kind == "foreign_related":
                        new, action = await upsert("学生希望采用新的讲解风格", related_memory_id=uuid4(), suggested_action="supersede")
                        assert action == "pending" and new.lifecycle_meta["review_reason"] == "unknown_related_memory"
                    elif kind == "scope_isolation":
                        items = await MemoryRetrievalService(db).retrieve(user_id=owner, course_id=uuid4(), question="栈")
                        assert old.id not in {item.id for item in items}
                    else:
                        evidence = await service.evidence_records(old.id, owner)
                        assert any(item["source_id"] == str(source.id) and item["excerpt"] == "我喜欢用图解释" for item in evidence)
                    await db.commit()
                    result["passed"] = True
                except Exception as exc:
                    await db.rollback()
                    result["error"] = f"{type(exc).__name__}: {exc}"
                results.append(result)
                print(result["id"], "PASS" if result["passed"] else result["error"], flush=True)
    report = {"finished_at": datetime.now(UTC).isoformat(), "type": "deterministic PostgreSQL service integration, not blind/model evaluation",
              "evaluation_user_id": str(owner), "passed": sum(item["passed"] for item in results), "total": len(results), "results": results}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report["passed"] == report["total"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", required=True, type=UUID)
    parser.add_argument("--output", type=Path, default=ROOT / "data/seed_knowledge/data_structure/eval/baselines/memory_lifecycle_acceptance.json")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(0 if asyncio.run(evaluate(args.user_id, args.output)) else 1)
