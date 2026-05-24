from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.llm.schemas import ChatMessage, ChatResponse, LLMCallContext, LLMModelConfig
from app.services.llm_log_service import LLMLogService


class FakeDB:
    def __init__(self) -> None:
        self.items: list[object] = []

    def add(self, item: object) -> None:
        self.items.append(item)

    async def flush(self) -> None:
        return None


def test_llm_log_service_records_success_call() -> None:
    asyncio.run(_test_llm_log_service_records_success_call())


async def _test_llm_log_service_records_success_call() -> None:
    db = FakeDB()
    service = LLMLogService(db)  # type: ignore[arg-type]

    log = await service.record_call(
        provider="mock",
        model_name="mock-learning-model",
        operation="chat",
        messages=[ChatMessage(role="user", content="Bearer secret-token 请解释栈")],
        texts=None,
        model_config=LLMModelConfig(model="mock-learning-model"),
        context=LLMCallContext(user_id=uuid4()),
        response=ChatResponse(
            content="栈是后进先出。",
            model="mock-learning-model",
            usage={"prompt_tokens": 4, "completion_tokens": 6, "total_tokens": 10},
        ),
        status="success",
        error_message=None,
        latency_ms=12,
        request_kwargs={"api_key": "should-not-log", "temperature": 0.3},
    )

    assert db.items == [log]
    assert log.status == "success"
    assert log.total_tokens == 10
    payload_text = str(log.request_payload)
    assert "secret-token" not in payload_text
    assert "should-not-log" not in payload_text


def test_llm_log_service_records_failed_call() -> None:
    asyncio.run(_test_llm_log_service_records_failed_call())


async def _test_llm_log_service_records_failed_call() -> None:
    db = FakeDB()
    service = LLMLogService(db)  # type: ignore[arg-type]

    log = await service.record_call(
        provider="openai_compatible",
        model_name="qwen",
        operation="chat",
        messages=[ChatMessage(role="user", content="测试")],
        texts=None,
        model_config=None,
        context=LLMCallContext(),
        response=None,
        status="failed",
        error_message="Authorization: Bearer abcdefg",
        latency_ms=5,
        request_kwargs={},
    )

    assert log.status == "failed"
    assert "abcdefg" not in (log.error_message or "")
