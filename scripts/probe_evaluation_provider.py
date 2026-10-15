"""Budgeted provider health probe without printing credentials or request URLs."""
import asyncio
import logging
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import settings
from app.llm.adapters.openai_compatible import OpenAICompatibleLLMProvider
from app.llm.schemas import ChatMessage
from evaluation_budget import BudgetProvider, EvaluationLedger

async def main():
    logging.getLogger("app.llm.adapters.openai_compatible").setLevel(logging.CRITICAL)
    ledger = EvaluationLedger(ROOT / "data/seed_knowledge/data_structure/eval/quality_v1/budget.sqlite")
    provider = BudgetProvider(OpenAICompatibleLLMProvider(api_key=settings.llm_api_key, base_url=settings.llm_base_url,
        model=settings.llm_model_name, timeout=20), ledger)
    provider.case_id = "provider-health"
    try:
        response = await provider.chat([ChatMessage(role="user", content="只回答OK")], max_tokens=8, thinking={"type": "disabled"})
        print({"ok": bool(response.content), "model": response.model, "usage": response.usage})
    except Exception as error:
        cause = error.__cause__
        print({"error": type(error).__name__, "cause": type(cause).__name__,
               "status": getattr(getattr(cause, "response", None), "status_code", None),
               "diagnostic": str(cause)[:100] if getattr(cause, "response", None) is None else "HTTP error"})

if __name__ == "__main__":
    if sys.platform == "win32": asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
