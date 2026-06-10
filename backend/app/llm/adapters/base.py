from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.llm.schemas import (
    ChatMessage,
    ChatResponse,
    EmbeddingResponse,
    LLMModelConfig,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class BaseLLMProvider(ABC):
    provider_name = "base"

    @abstractmethod
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
        ...

    async def structured_chat(
        self,
        messages: list[ChatMessage],
        response_model: type[T],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        model_config: LLMModelConfig | None = None,
        max_retries: int = 2,
        **kwargs: object,
    ) -> T:
        """Call LLM with structured output: validates response against a Pydantic model.

        Retries up to *max_retries* times on validation failure, appending the
        error detail so the LLM can self-correct.
        """
        schema = response_model.model_json_schema()
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": response_model.__name__,
                "schema": schema,
            },
        }
        merged_kwargs: dict[str, Any] = {**kwargs, "response_format": response_format}

        last_error: str | None = None
        chat_messages = list(messages)

        for attempt in range(max_retries + 1):
            # On retry, append the validation error so the LLM can fix it
            if last_error and attempt > 0:
                chat_messages = [
                    *messages,
                    ChatMessage(
                        role="user",
                        content=(
                            f"上次输出校验失败，错误如下：\n{last_error}\n\n"
                            "请严格按照要求的 JSON Schema 重新输出，不要输出额外文字。"
                        ),
                    ),
                ]

            response = await self.chat(
                chat_messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                model_config=model_config,
                **merged_kwargs,
            )

            parsed = self._parse_structured_response(response.content, response_model)
            if parsed is not None:
                return parsed

            last_error = (
                f"第 {attempt + 1} 次尝试：LLM 返回内容无法匹配 "
                f"{response_model.__name__} schema。原始内容前 500 字符：\n"
                f"{response.content[:500]}"
            )
            logger.warning("structured_chat validation failed (attempt %d): %s", attempt + 1, last_error)

        # All retries exhausted — return the error detail so callers can handle it
        raise ValueError(
            f"structured_chat: {max_retries + 1} 次尝试后仍无法获得合法的 "
            f"{response_model.__name__} 输出。最后错误：{last_error}"
        )

    @staticmethod
    def _parse_structured_response(content: str, model: type[T]) -> T | None:
        """Try to parse LLM output as the given Pydantic model."""
        cleaned = _strip_json_fence(content)
        # Try direct parse first
        for text in (cleaned, content):
            try:
                data = json.loads(text)
                return model.model_validate(data)
            except (json.JSONDecodeError, ValidationError):
                continue
        # Try extracting JSON from markdown / prose
        for start_char, end_char in [("{", "}"), ("[", "]")]:
            start = cleaned.find(start_char)
            end = cleaned.rfind(end_char)
            if start != -1 and end > start:
                try:
                    data = json.loads(cleaned[start : end + 1])
                    return model.model_validate(data)
                except (json.JSONDecodeError, ValidationError):
                    continue
        return None

    @abstractmethod
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
        ...
        yield ""

    @abstractmethod
    async def embedding(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        model_config: LLMModelConfig | None = None,
        **kwargs: object,
    ) -> EmbeddingResponse:
        ...


def _strip_json_fence(text: str) -> str:
    """Remove ```json ... ``` fences if present."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = [line for line in cleaned.splitlines() if not line.strip().startswith("```")]
        return "\n".join(lines).strip()
    return cleaned
