"""Isolated local evaluation server; real model calls share the authorized ledger."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
# Process-local overrides only. The user's .env files are never written.
os.environ["REDIS_URL"] = "redis://localhost:6379/14"
os.environ["AGENT_INLINE_FALLBACK"] = "true"
os.environ["AGENT_INLINE_FALLBACK_DELAY_SECONDS"] = "0.2"

import app.llm.provider as provider_module
from evaluation_budget import BudgetProvider, EvaluationLedger
ledger = EvaluationLedger(ROOT / "data/seed_knowledge/data_structure/eval/quality_v1/budget.sqlite")
original = provider_module.get_llm_provider

def budgeted_provider(*args, **kwargs):
    kwargs["allow_mock_fallback"] = False
    wrapped = BudgetProvider(original(*args, **kwargs), ledger)
    wrapped.case_id = "http-continuous-context"
    return wrapped

provider_module.get_llm_provider = budgeted_provider
from app.main import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8017, log_level="warning", access_log=False)
