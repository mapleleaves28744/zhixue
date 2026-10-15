"""Actual MemoryAgent extraction on automatically labeled synthetic statements."""
from __future__ import annotations
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.agents.memory_agent import MemoryAgent
from app.agents.structured_outputs import MemoryReflectOutput
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.course import Course
from app.llm.adapters.openai_compatible import OpenAICompatibleLLMProvider
from app.services.memory_facts import canonical_preference, learning_memory_source_allowed
from evaluation_budget import EvaluationLedger, BudgetProvider, BudgetExceeded
from evaluate_context_quality import BASE, append

CASES = [
    ("我喜欢用图解释知识点，请长期记住。", "diagrams"),
    ("我希望学习时能多一些可视化解释，请记住这个学习偏好。", "diagrams"),
    ("请长期记住，我喜欢用具体案例理解抽象概念。", "examples"),
    ("我喜欢举例子说明知识点。", "examples"),
    ("我喜欢分步骤解释复杂算法。", "steps"),
    ("我喜欢一步一步讲解。", "steps"),
    ("我喜欢详细讲解。", "detailed"),
    ("记住我喜欢简短回答。", "concise"),
    ("你好，今天辛苦了。", None),
    ("谢谢，明白了。", None),
    ("这次请简短讲解栈。", None),
    ("后续用英文回答。", None),
    ("本次对话先给例子。", None),
    ("接下来分点回答。", None),
    ("栈和队列的区别是什么？", None),
    ("只给这道题详细解释，不要长期记住。", None),
    ("这次给我看一个示意图，不代表我的长期偏好。", None),
    ("讲义原文是：我喜欢用图解释。请说明这句话含义，不要当成我的偏好。", None),
    ("示例角色小明说他喜欢简短讲解，这不是我的偏好。", None),
    ("我的测试手机号是13800000000，请不要保存。", None),
]


async def main(release: bool = False):
    if "qwen" not in settings.llm_model_name.lower() or not settings.llm_api_key:
        raise RuntimeError("Real Qwen required")
    manifest = BASE / "memory-extraction-fixtures.json"
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if [(case["text"], case["expected"]) for case in data["cases"]] != CASES:
            raise ValueError("Frozen extraction labels changed")
    else:
        memory = json.loads((BASE / "memory-fixtures.json").read_text(encoding="utf-8"))
        data = {"owner": memory["owner_id"], "automatic_synthetic_labels": True, "independent_human_review": False, "cases": []}
        async with AsyncSessionLocal() as db:
            course = Course(owner_id=UUID(data["owner"]), title="合成记忆提取质量", visibility="private", status="active")
            db.add(course)
            await db.commit()
            data["course"] = str(course.id)
        data["cases"] = [{"id": f"extract-{index:02}", "source_id": str(uuid4()), "text": text, "expected": expected}
                         for index, (text, expected) in enumerate(CASES)]
        manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    output = BASE / ("memory-extraction-release-results.jsonl" if release else "memory-extraction-results.jsonl")
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()] if output.exists() else []
    done = {row["id"] for row in rows}
    ledger = EvaluationLedger(BASE / "budget.sqlite")
    provider = BudgetProvider(OpenAICompatibleLLMProvider(api_key=settings.llm_api_key, base_url=settings.llm_base_url,
        model=settings.llm_model_name, timeout=90), ledger)
    for case in data["cases"]:
        if case["id"] in done:
            continue
        provider.case_id = case["id"]
        row = {**case, "passed": False, "tp": 0, "fp": 0, "fn": int(case["expected"] is not None)}
        before = len(provider.responses)
        try:
            record = SimpleNamespace(id=UUID(case["source_id"]), course_id=UUID(data["course"]), event_type="chat", event_payload={"question": case["text"]})
            async with AsyncSessionLocal() as db:
                candidates = await MemoryAgent(db)._llm_reflect(provider, [record], user_id=UUID(data["owner"]))
            if provider.budget_exhausted:
                raise BudgetExceeded("Memory fallback swallowed budget refusal")
            responses = provider.responses[before:]
            parsed = provider._parse_structured_response(responses[-1].content, MemoryReflectOutput) if responses else None
            source_guarded = not learning_memory_source_allowed(case["text"])
            if parsed is None and not (source_guarded and not candidates):
                raise ValueError("Real extraction unavailable; rule fallback is not counted as model success")
            row["extraction_method"] = "source_guard" if source_guarded else "real_model"
            matched = False
            for candidate in candidates:
                valid = (case["expected"] is not None and not matched
                    and candidate.get("memory_type") == "preference"
                    and canonical_preference(candidate.get("content", "")) == "preference:explanation:" + case["expected"]
                    and candidate.get("evidence") == [case["source_id"]]
                    and candidate.get("suggested_action") != "ignore")
                if valid:
                    row["tp"] += 1
                    matched = True
                elif candidate.get("suggested_action") != "ignore":
                    row["fp"] += 1
            row["fn"] = int(case["expected"] is not None and not matched)
            row["passed"] = row["fp"] == 0 and row["fn"] == 0
            row["candidates"] = candidates
            row["usage"] = [response.usage for response in responses]
        except BudgetExceeded:
            raise
        except Exception as exc:
            row["error_type"] = type(exc).__name__
        append(output, row)
        rows.append(row)
        print(case["id"], "PASS" if row["passed"] else "FAIL", flush=True)
    tp, fp, fn = (sum(row[key] for row in rows) for key in ("tp", "fp", "fn"))
    report = {"finished_at": datetime.now(UTC).isoformat(), "automatic_synthetic_labels": True,
        "independent_human_review": False, "scope": "actual MemoryAgent extraction; synthetic source records; no natural-user quality claim",
        "total": len(rows), "passed": sum(row["passed"] for row in rows), "tp": tp, "fp": fp, "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else None, "recall": tp / (tp + fn) if tp + fn else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
        "negative_no_output": sum(row["passed"] for row in rows if row["expected"] is None),
        "negative_total": sum(row["expected"] is None for row in rows), "budget": ledger.snapshot()}
    report["evaluation_status"] = "post-fix regression on observed synthetic statements" if release else "initial synthetic evaluation"
    report["scope"] = "MemoryAgent extraction including source guards; synthetic source records; not natural-user quality"
    report_path = BASE / ("memory-extraction-release-report.json" if release else "memory-extraction-report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    if sys.platform == "win32": asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main(release="--release" in sys.argv))
