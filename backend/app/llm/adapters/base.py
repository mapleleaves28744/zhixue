from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.llm.schemas import (
    ChatMessage,
    ChatResponse,
    EmbeddingResponse,
    LLMModelConfig,
)


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
