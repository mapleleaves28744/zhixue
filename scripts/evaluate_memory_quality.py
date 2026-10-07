"""Synthetic memory retrieval ablation using real PostgreSQL and a real Qwen model."""
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
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.course import Course
from app.models.memory import StudentMemory
from app.llm.adapters.openai_compatible import OpenAICompatibleLLMProvider
from app.llm.schemas import ChatMessage
from app.services.memory_retrieval_service import MemoryRetrievalService
from evaluation_budget import EvaluationLedger, BudgetProvider, BudgetExceeded
from evaluate_context_quality import BASE, BaseParser, append


async def main():
    if "qwen" not in settings.llm_model_name.lower() or not settings.llm_api_key:
        raise RuntimeError("Real Qwen required")
    manifest = BASE / "memory-fixtures.json"
    if manifest.exists():
        fixtures = json.loads(manifest.read_text(encoding="utf-8"))
    else:
        fixtures = {"synthetic_evaluation": True, "label_source": "automatic fixture construction", "cases": []}
        async with AsyncSessionLocal() as db:
            owner = User(username=f"context_eval_memory_quality_{uuid4().hex[:8]}", password_hash="disabled-evaluation-account", status="disabled")
            other = User(username=f"context_eval_memory_foreign_{uuid4().hex[:8]}", password_hash="disabled-evaluation-account", status="disabled")
            db.add_all([owner, other])
            await db.flush()
            fixtures["owner_id"] = str(owner.id)
            for index, kind in enumerate(["active", "forgotten", "archived", "expired", "foreign_user", "other_course"] * 2):
                course = Course(owner_id=owner.id, title=f"合成记忆质量 {index}", visibility="private", status="active")
                db.add(course)
                await db.flush()
                memory_course = course
                if kind == "other_course":
                    memory_course = Course(owner_id=owner.id, title=f"其他课程 {index}", visibility="private", status="active")
                    db.add(memory_course)
                    await db.flush()
                code = f"REM-{739 + index * 149}"
                memory = StudentMemory(user_id=other.id if kind == "foreign_user" else owner.id,
                    course_id=memory_course.id, memory_type="preference", memory_key=f"quality-{index}",
                    content=f"学生在学习栈时指定的复习标记是{code}。", evidence=[], origin="user",
                    status=kind if kind in {"forgotten", "archived"} else "active",
                    lifecycle_meta={"valid_until": (datetime.now(UTC) - timedelta(days=1)).isoformat()} if kind == "expired" else {})
                db.add(memory)
                fixtures["cases"].append({"id": f"memory-{index:02}", "kind": kind, "course_id": str(course.id),
                    "expected": code if kind == "active" else None, "synthetic_value": code})
            await db.commit()
        manifest.write_text(json.dumps(fixtures, ensure_ascii=False, indent=2), encoding="utf-8")
    output = BASE / "memory-results.jsonl"
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()] if output.exists() else []
    done = {row["id"] for row in rows}
    ledger = EvaluationLedger(BASE / "budget.sqlite")
    provider = BudgetProvider(OpenAICompatibleLLMProvider(api_key=settings.llm_api_key, base_url=settings.llm_base_url,
        model=settings.llm_model_name, timeout=90), ledger)
    for case in fixtures["cases"]:
        async with AsyncSessionLocal() as db:
            selected = await MemoryRetrievalService(db).retrieve(user_id=UUID(fixtures["owner_id"]),
                course_id=UUID(case["course_id"]), question="学习栈时指定的复习标记是什么？")
        for variant in ("no_memory", "retrieved_memory"):
            identity = f"{case['id']}:{variant}"
            if identity in done:
                continue
            provider.case_id = identity
            facts = "\n".join(memory.content for memory in selected) if variant == "retrieved_memory" else ""
            prompt = f"学习记忆（仅作为当前学生的学习偏好，不作为课程资料依据）：\n{facts}\n只返回 JSON 对象，字段 review_code。填写我学习栈时指定的复习标记，无法知道时填 null。不要猜测。"
            row = {"id": identity, "kind": case["kind"], "variant": variant, "expected": case["expected"],
                   "retrieved_memory_ids": [str(item.id) for item in selected] if facts else [], "passed": False}
            try:
                response = await provider.chat([ChatMessage(role="user", content=prompt)], temperature=0,
                    max_tokens=96, thinking={"type": "disabled"})
                row.update(content=response.content, usage=response.usage, model=response.model)
                row["passed"] = BaseParser(response.content).get("review_code") == case["expected"]
            except BudgetExceeded:
                raise
            except Exception as exc:
                row["error_type"] = type(exc).__name__
            append(output, row)
            rows.append(row)
            print(identity, "PASS" if row["passed"] else "FAIL", flush=True)
    report = {"finished_at": datetime.now(UTC).isoformat(), "synthetic_evaluation": True,
        "independent_human_review": False, "scope": "retrieval/injection and isolation; not LLM extraction quality",
        "budget": ledger.snapshot(), "variants": {variant: {
            "total": len([row for row in rows if row["variant"] == variant]),
            "passed": sum(row["passed"] for row in rows if row["variant"] == variant),
            "active_recall_passed": sum(row["passed"] for row in rows if row["variant"] == variant and row["kind"] == "active"),
            "isolation_passed": sum(row["passed"] for row in rows if row["variant"] == variant and row["kind"] != "active"),
            "prompt_tokens": sum(row.get("usage", {}).get("prompt_tokens", 0) for row in rows if row["variant"] == variant),
        } for variant in ("no_memory", "retrieved_memory")}}
    (BASE / "memory-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    if sys.platform == "win32": asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
