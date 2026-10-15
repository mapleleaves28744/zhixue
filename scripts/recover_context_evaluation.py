"""Retry transport-failed context cases only, preserving all original outcomes."""
import asyncio
import json
import logging
import sys
from pathlib import Path
from evaluate_context_quality import BASE, evaluate_context
from evaluation_budget import EvaluationLedger, BudgetProvider
from app.core.config import settings
from app.llm.adapters.openai_compatible import OpenAICompatibleLLMProvider

async def main():
    original = [json.loads(line) for line in (BASE / "holdout-release-results.jsonl").read_text(encoding="utf-8").splitlines()]
    destination = BASE / "context-network-recovery-results.jsonl"
    retries = [json.loads(line) for line in destination.read_text(encoding="utf-8").splitlines()] if destination.exists() else []
    done = {row["id"] for row in original if row["category"] != "context" or not row.get("error_type")}
    done |= {row["id"] for row in retries}
    ledger = EvaluationLedger(BASE / "budget.sqlite")
    provider = BudgetProvider(OpenAICompatibleLLMProvider(api_key=settings.llm_api_key, base_url=settings.llm_base_url,
        model=settings.llm_model_name, timeout=90), ledger)
    logging.getLogger("app.llm.adapters.openai_compatible").setLevel(logging.CRITICAL)
    try:
        await evaluate_context(provider, destination, done)
    finally:
        retries = [json.loads(line) for line in destination.read_text(encoding="utf-8").splitlines()] if destination.exists() else []
        latest = {row["id"]: row for row in original if row["category"] == "context"}
        latest.update({row["id"]: row for row in retries})
        report = {"scope": "network recovery; observed synthetic cases, not a new blind evaluation",
            "original_transport_failures": sum(bool(row.get("error_type")) for row in original if row["category"] == "context"),
            "recovery_attempts": len(retries), "recovery_transport_failures": sum(bool(row.get("error_type")) for row in retries),
            "groups": {}, "budget": ledger.snapshot()}
        for variant in ("no_history", "recent_only", "raw_history", "compacted"):
            selected = [row for row in latest.values() if row["variant"] == variant]
            report["groups"][variant] = {"total": len(selected), "passed": sum(row["passed"] for row in selected),
                "prompt_tokens": sum(row.get("usage", {}).get("prompt_tokens", 0) for row in selected),
                "transport_failures": sum(bool(row.get("error_type")) for row in selected)}
        (BASE / "context-network-recovery-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    if sys.platform == "win32": asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
