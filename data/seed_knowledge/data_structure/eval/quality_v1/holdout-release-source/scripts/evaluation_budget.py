"""Durable, transactional evaluation budget; no credentials or prompts in the ledger."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from uuid import uuid4

from app.llm.adapters.base import BaseLLMProvider
from app.llm.schemas import ChatMessage


class BudgetExceeded(RuntimeError):
    pass


class EvaluationLedger:
    def __init__(self, path: Path, limit: int = 3_000_000) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS budget (id INTEGER PRIMARY KEY CHECK(id=1), cap INTEGER NOT NULL)")
            db.execute("INSERT OR IGNORE INTO budget VALUES (1, ?)", (limit,))
            if db.execute("SELECT cap FROM budget").fetchone()[0] != limit:
                raise ValueError("An existing ledger cannot silently change its budget")
            db.execute("""CREATE TABLE IF NOT EXISTS calls (
                id TEXT PRIMARY KEY, case_id TEXT NOT NULL, reserved INTEGER NOT NULL,
                charged INTEGER NOT NULL, status TEXT NOT NULL, model TEXT,
                prompt_tokens INTEGER, completion_tokens INTEGER, elapsed REAL,
                error_type TEXT, created REAL NOT NULL)""")

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def reserve(self, case_id: str, amount: int) -> str:
        if amount < 1:
            raise ValueError("Reservation must be positive")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cap = db.execute("SELECT cap FROM budget").fetchone()[0]
            used = db.execute("SELECT COALESCE(SUM(charged),0) FROM calls").fetchone()[0]
            if used + amount > cap:
                raise BudgetExceeded(f"Evaluation budget exhausted: {used}/{cap}, requested {amount}")
            identity = uuid4().hex
            db.execute("INSERT INTO calls(id,case_id,reserved,charged,status,created) VALUES (?,?,?,?,'pending',?)",
                       (identity, case_id, amount, amount, time.time()))
            return identity

    def finish(self, identity: str, *, response=None, elapsed: float, error: Exception | None = None) -> None:
        # Missing usage, crashes and errors retain the entire reservation.
        usage = response.usage if response else {}
        prompt = int(usage.get("prompt_tokens") or 0)
        output = int(usage.get("completion_tokens") or 0)
        total = int(usage.get("total_tokens") or prompt + output)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            reserved, status = db.execute("SELECT reserved,status FROM calls WHERE id=?", (identity,)).fetchone()
            if status != "pending":
                raise ValueError("A ledger call can only be settled once")
            # Never undercount if the upstream reports usage beyond the reservation.
            db.execute("""UPDATE calls SET charged=?,status=?,model=?,prompt_tokens=?,
                        completion_tokens=?,elapsed=?,error_type=? WHERE id=?""",
                       (total if total > 0 else reserved, "failed" if error else "succeeded",
                        response.model if response else None, prompt, output, elapsed,
                        type(error).__name__ if error else None, identity))

    def snapshot(self) -> dict:
        with self.connect() as db:
            rows = db.execute("SELECT status,COUNT(*),SUM(charged) FROM calls GROUP BY status").fetchall()
            return {"cap": db.execute("SELECT cap FROM budget").fetchone()[0],
                    "charged_tokens": sum(row[2] for row in rows),
                    "calls": {row[0]: {"count": row[1], "charged_tokens": row[2]} for row in rows},
                    "unknown_usage_policy": "failed/pending/missing usage charged full reservation"}


class BudgetProvider(BaseLLMProvider):
    """Structured retries invoke this chat method and therefore each get a reservation."""
    def __init__(self, inner: BaseLLMProvider, ledger: EvaluationLedger) -> None:
        self.inner = inner
        self.ledger = ledger
        self.provider_name = inner.provider_name
        self.case_id = "unspecified"
        self.responses = []
        self.budget_exhausted = False

    async def chat(self, messages: list[ChatMessage], *, max_tokens: int = 2048, **kwargs):
        config = kwargs.get("model_config")
        output = config.max_tokens if config else max_tokens
        # Byte bound is deliberately stronger than the production heuristic.
        # Includes schema/kwargs and chat framing. Only one HTTP attempt per reservation.
        payload = [message.as_openai_dict() for message in messages]
        amount = len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + output + 1024
        amount += len(json.dumps({k: v for k, v in kwargs.items() if k != "model_config"}, default=str).encode("utf-8"))
        try:
            identity = self.ledger.reserve(self.case_id, amount)
        except BudgetExceeded:
            self.budget_exhausted = True
            raise
        started = time.monotonic()
        try:
            response = await self.inner.chat(messages, max_tokens=max_tokens, **{**kwargs, "transport_attempts": 1})
        except BaseException as exc:
            self.ledger.finish(identity, elapsed=time.monotonic() - started, error=exc)
            raise
        self.ledger.finish(identity, response=response, elapsed=time.monotonic() - started)
        self.responses.append(response)
        return response

    async def stream_chat(self, *args, **kwargs):
        raise NotImplementedError("Evaluation uses fully accounted non-streaming responses")
        yield ""

    async def embedding(self, *args, **kwargs):
        raise NotImplementedError("Embedding must have a separately accounted evaluation")
