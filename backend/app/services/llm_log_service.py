from __future__ import annotations

import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.schemas import (
    ChatMessage,
    ChatResponse,
    EmbeddingResponse,
    LLMCallContext,
    LLMModelConfig,
)
from app.models.llm_log import LLMCallLog


SENSITIVE_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"(api[_-]?key|authorization|token|secret)\s*[:=]\s*[^,\s}]+", re.IGNORECASE),
]


class LLMLogService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record_call(
        self,
        *,
        provider: str,
        model_name: str,
        operation: str,
        messages: list[ChatMessage] | None,
        texts: list[str] | None,
        model_config: LLMModelConfig | None,
        context: LLMCallContext,
        response: ChatResponse | None = None,
        embedding_response: EmbeddingResponse | None = None,
        status: str,
        error_message: str | None,
        latency_ms: int | None,
        request_kwargs: dict[str, object] | None = None,
    ) -> LLMCallLog:
        usage = response.usage if response is not None else embedding_response.usage if embedding_response else {}
        log = LLMCallLog(
            user_id=context.user_id,
            course_id=context.course_id,
            agent_run_id=context.agent_run_id,
            provider=provider,
            model_name=model_name,
            prompt_version_id=context.prompt_version_id,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            request_payload=self.build_request_summary(
                operation=operation,
                messages=messages,
                texts=texts,
                model_config=model_config,
                request_kwargs=request_kwargs or {},
            ),
            response_payload=self.build_response_summary(
                response=response,
                embedding_response=embedding_response,
            ),
            status=status,
            error_message=self.sanitize_text(error_message) if error_message else None,
            latency_ms=latency_ms,
        )
        self.db.add(log)
        await self.db.flush()
        return log

    def build_request_summary(
        self,
        *,
        operation: str,
        messages: list[ChatMessage] | None,
        texts: list[str] | None,
        model_config: LLMModelConfig | None,
        request_kwargs: dict[str, object],
    ) -> dict[str, Any]:
        safe_kwargs = {
            key: self.sanitize_text(str(value))[:200]
            for key, value in request_kwargs.items()
            if key not in {"api_key", "authorization", "token", "secret"}
        }
        return {
            "operation": operation,
            "message_count": len(messages or []),
            "messages": [
                {
                    "role": message.role,
                    "content_preview": self.sanitize_text(message.content)[:300],
                    "content_length": len(message.content),
                }
                for message in (messages or [])[:10]
            ],
            "text_count": len(texts or []),
            "texts": [
                {
                    "content_preview": self.sanitize_text(text)[:300],
                    "content_length": len(text),
                }
                for text in (texts or [])[:10]
            ],
            "model_config": {
                "model": model_config.model if model_config else None,
                "temperature": model_config.temperature if model_config else None,
                "max_tokens": model_config.max_tokens if model_config else None,
                "embedding_model": model_config.embedding_model if model_config else None,
            },
            "kwargs": safe_kwargs,
        }

    def build_response_summary(
        self,
        *,
        response: ChatResponse | None,
        embedding_response: EmbeddingResponse | None,
    ) -> dict[str, Any]:
        if response is not None:
            return {
                "content_preview": self.sanitize_text(response.content)[:500],
                "content_length": len(response.content),
                "usage": response.usage,
                "model": response.model,
            }
        if embedding_response is not None:
            return {
                "embedding_count": len(embedding_response.embeddings),
                "embedding_dimension": len(embedding_response.embeddings[0])
                if embedding_response.embeddings
                else 0,
                "usage": embedding_response.usage,
                "model": embedding_response.model,
            }
        return {}

    def sanitize_text(self, value: str) -> str:
        sanitized = value
        for pattern in SENSITIVE_PATTERNS:
            sanitized = pattern.sub("[REDACTED]", sanitized)
        return sanitized
