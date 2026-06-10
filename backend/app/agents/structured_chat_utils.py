from __future__ import annotations

import logging
from typing import TypeVar

from pydantic import BaseModel

from app.core.config import settings
from app.llm.schemas import ChatMessage

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


async def call_structured_chat(
    provider: object,
    messages: list[ChatMessage],
    response_model: type[T],
    *,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    max_retries: int | None = None,
    **kwargs: object,
) -> T:
    retries = settings.llm_structured_max_retries if max_retries is None else max_retries
    return await provider.structured_chat(  # type: ignore[attr-defined]
        messages,
        response_model,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=retries,
        **kwargs,
    )


async def call_structured_chat_or_none(
    provider: object,
    messages: list[ChatMessage],
    response_model: type[T],
    *,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    max_retries: int | None = None,
    **kwargs: object,
) -> T | None:
    try:
        return await call_structured_chat(
            provider,
            messages,
            response_model,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=max_retries,
            **kwargs,
        )
    except ValueError as exc:
        logger.warning("structured_chat failed for %s: %s", response_model.__name__, exc)
        return None
