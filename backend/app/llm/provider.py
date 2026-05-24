from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from time import perf_counter
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.llm.adapters.base import BaseLLMProvider
from app.llm.schemas import (
    ChatMessage,
    ChatResponse,
    EmbeddingResponse,
    LLMCallContext,
    LLMModelConfig,
)

logger = logging.getLogger(__name__)


class LoggingLLMProvider(BaseLLMProvider):
    provider_name = "logged"

    def __init__(
        self,
        inner: BaseLLMProvider,
        *,
        db: AsyncSession | None = None,
        context: LLMCallContext | None = None,
    ) -> None:
        self.inner = inner
        self.db = db
        self.context = context or LLMCallContext()

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        model_config: LLMModelConfig | None = None,
        **kwargs: object,
    ) -> ChatResponse:
        started = perf_counter()
        call_context = self._context_from_kwargs(kwargs)
        try:
            response = await self.inner.chat(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                model_config=model_config,
                **kwargs,
            )
        except Exception as exc:
            await self._log_call(
                operation="chat",
                messages=messages,
                texts=None,
                model=model,
                model_config=model_config,
                status="failed",
                latency_ms=self._latency(started),
                context=call_context,
                error_message=str(exc),
                request_kwargs=kwargs,
            )
            if isinstance(exc, BusinessException):
                raise
            raise BusinessException(
                code=ErrorCode.LLM_CALL_FAILED,
                detail=str(exc),
                status_code=500,
            ) from exc

        await self._log_call(
            operation="chat",
            messages=messages,
            texts=None,
            model=response.model or model,
            model_config=model_config,
            status="success",
            latency_ms=self._latency(started),
            context=call_context,
            response=response,
            request_kwargs=kwargs,
        )
        return response

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        model_config: LLMModelConfig | None = None,
        **kwargs: object,
    ) -> AsyncIterator[str]:
        started = perf_counter()
        chunks: list[str] = []
        call_context = self._context_from_kwargs(kwargs)
        try:
            async for chunk in self.inner.stream_chat(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                model_config=model_config,
                **kwargs,
            ):
                chunks.append(chunk)
                yield chunk
        except Exception as exc:
            await self._log_call(
                operation="stream_chat",
                messages=messages,
                texts=None,
                model=model,
                model_config=model_config,
                status="failed",
                latency_ms=self._latency(started),
                context=call_context,
                error_message=str(exc),
                request_kwargs=kwargs,
            )
            if isinstance(exc, BusinessException):
                raise
            raise BusinessException(
                code=ErrorCode.LLM_CALL_FAILED,
                detail=str(exc),
                status_code=500,
            ) from exc

        response = ChatResponse(
            content="".join(chunks),
            model=model or (model_config.model if model_config else "") or settings.llm_model_name,
            provider=self.inner.provider_name,
        )
        await self._log_call(
            operation="stream_chat",
            messages=messages,
            texts=None,
            model=response.model,
            model_config=model_config,
            status="success",
            latency_ms=self._latency(started),
            context=call_context,
            response=response,
            request_kwargs=kwargs,
        )

    async def embedding(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        model_config: LLMModelConfig | None = None,
        **kwargs: object,
    ) -> EmbeddingResponse:
        started = perf_counter()
        call_context = self._context_from_kwargs(kwargs)
        try:
            response = await self.inner.embedding(
                texts,
                model=model,
                model_config=model_config,
                **kwargs,
            )
        except Exception as exc:
            await self._log_call(
                operation="embedding",
                messages=None,
                texts=texts,
                model=model,
                model_config=model_config,
                status="failed",
                latency_ms=self._latency(started),
                context=call_context,
                error_message=str(exc),
                request_kwargs=kwargs,
            )
            if isinstance(exc, BusinessException):
                raise
            raise BusinessException(
                code=ErrorCode.LLM_CALL_FAILED,
                detail=str(exc),
                status_code=500,
            ) from exc

        await self._log_call(
            operation="embedding",
            messages=None,
            texts=texts,
            model=response.model or model,
            model_config=model_config,
            status="success",
            latency_ms=self._latency(started),
            context=call_context,
            embedding_response=response,
            request_kwargs=kwargs,
        )
        return response

    def _context_from_kwargs(self, kwargs: dict[str, object]) -> LLMCallContext:
        return LLMCallContext(
            user_id=self._uuid(kwargs.get("user_id")) or self.context.user_id,
            course_id=self._uuid(kwargs.get("course_id")) or self.context.course_id,
            agent_run_id=self._uuid(kwargs.get("agent_run_id")) or self.context.agent_run_id,
            prompt_version_id=self._uuid(kwargs.get("prompt_version_id")) or self.context.prompt_version_id,
        )

    async def _log_call(
        self,
        *,
        operation: str,
        messages: list[ChatMessage] | None,
        texts: list[str] | None,
        model: str | None,
        model_config: LLMModelConfig | None,
        status: str,
        latency_ms: int,
        context: LLMCallContext,
        response: ChatResponse | None = None,
        embedding_response: EmbeddingResponse | None = None,
        error_message: str | None = None,
        request_kwargs: dict[str, object] | None = None,
    ) -> None:
        if self.db is None:
            return
        try:
            from app.services.llm_log_service import LLMLogService

            await LLMLogService(self.db).record_call(
                provider=self.inner.provider_name,
                model_name=model or (model_config.model if model_config else None) or settings.llm_model_name,
                operation=operation,
                messages=messages,
                texts=texts,
                model_config=model_config,
                context=context,
                response=response,
                embedding_response=embedding_response,
                status=status,
                error_message=error_message,
                latency_ms=latency_ms,
                request_kwargs=request_kwargs or {},
            )
        except Exception:
            logger.exception("Failed to write LLM call log")

    def _latency(self, started: float) -> int:
        return int((perf_counter() - started) * 1000)

    def _uuid(self, value: object) -> UUID | None:
        if isinstance(value, UUID):
            return value
        if isinstance(value, str):
            try:
                return UUID(value)
            except ValueError:
                return None
        return None


def build_llm_provider() -> BaseLLMProvider:
    provider = settings.llm_provider.lower()
    if provider in ("openai", "compatible", "openai_compatible"):
        if not settings.llm_api_key:
            from app.llm.adapters.mock_provider import MockLLMProvider

            return MockLLMProvider()
        from app.llm.adapters.openai_compatible import OpenAICompatibleLLMProvider

        return OpenAICompatibleLLMProvider(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url or "https://api.openai.com/v1",
            model=settings.llm_model_name,
            timeout=settings.llm_timeout_seconds,
            embedding_model=settings.embedding_model,
            embedding_dimension=settings.embedding_dimension,
        )

    from app.llm.adapters.mock_provider import MockLLMProvider

    return MockLLMProvider()


def get_llm_provider(
    db: AsyncSession | None = None,
    user_id: UUID | None = None,
    course_id: UUID | None = None,
    agent_run_id: UUID | None = None,
    prompt_version_id: UUID | None = None,
) -> BaseLLMProvider:
    provider = build_llm_provider()
    if db is None:
        return provider
    return LoggingLLMProvider(
        provider,
        db=db,
        context=LLMCallContext(
            user_id=user_id,
            course_id=course_id,
            agent_run_id=agent_run_id,
            prompt_version_id=prompt_version_id,
        ),
    )
