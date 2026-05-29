from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.llm.adapters.base import BaseLLMProvider
from app.llm.schemas import ChatMessage, ChatResponse, EmbeddingResponse, LLMModelConfig

logger = logging.getLogger(__name__)


class OpenAICompatibleLLMProvider(BaseLLMProvider):
    """Adapter for OpenAI-compatible APIs (OpenAI, Tongyi, Zhipu, etc.)."""

    provider_name = "openai_compatible"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: int = 60,
        embedding_model: str | None = None,
        embedding_dimension: int = 1024,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._embedding_model = embedding_model or "text-embedding-3-small"
        self._embedding_dimension = embedding_dimension
        if "xiaomimimo.com" in self._base_url.lower():
            self.provider_name = "xiaomi_mimo"

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
        cfg = model_config or LLMModelConfig()
        payload = {
            "model": model or cfg.model or self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": cfg.temperature if model_config else temperature,
            "max_tokens": cfg.max_tokens if model_config else max_tokens,
        }
        try:
            async with httpx.AsyncClient(timeout=cfg.timeout_seconds or self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            logger.exception("OpenAI-compatible chat failed")
            raise BusinessException(
                code=ErrorCode.LLM_CALL_FAILED,
                detail=f"OpenAI-compatible chat 调用失败：{exc}",
                status_code=500,
            ) from exc

        try:
            choice = data["choices"][0]
            usage = data.get("usage", {})
            return ChatResponse(
                content=choice["message"]["content"],
                model=data.get("model", payload["model"]),
                usage={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                raw=data,
                provider=self.provider_name,
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise BusinessException(
                code=ErrorCode.LLM_CALL_FAILED,
                detail=f"OpenAI-compatible chat 响应格式异常：{exc}",
                status_code=500,
            ) from exc

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
        cfg = model_config or LLMModelConfig()
        payload = {
            "model": model or cfg.model or self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": cfg.temperature if model_config else temperature,
            "max_tokens": cfg.max_tokens if model_config else max_tokens,
            "stream": True,
        }
        try:
            async with httpx.AsyncClient(timeout=cfg.timeout_seconds or self._timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self._base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            logger.warning("Skip malformed stream chunk: %s", data_str[:200])
                            continue
        except httpx.HTTPError as exc:
            logger.exception("OpenAI-compatible stream_chat failed")
            raise BusinessException(
                code=ErrorCode.LLM_CALL_FAILED,
                detail=f"OpenAI-compatible stream_chat 调用失败：{exc}",
                status_code=500,
            ) from exc

    async def embedding(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        model_config: LLMModelConfig | None = None,
        **kwargs: object,
    ) -> EmbeddingResponse:
        cfg = model_config or LLMModelConfig()
        selected_model = model or cfg.embedding_model or self._embedding_model
        try:
            async with httpx.AsyncClient(timeout=cfg.timeout_seconds or self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/embeddings",
                    headers=self._headers(),
                    json={"model": selected_model, "input": texts},
                )
                resp.raise_for_status()
                data = resp.json()
            sorted_items = sorted(data["data"], key=lambda item: item["index"])
            usage = data.get("usage", {})
            return EmbeddingResponse(
                embeddings=[item["embedding"] for item in sorted_items],
                model=data.get("model", selected_model),
                usage={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                raw=data,
                provider=self.provider_name,
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            logger.exception("OpenAI-compatible embedding failed")
            raise BusinessException(
                code=ErrorCode.LLM_CALL_FAILED,
                detail=f"OpenAI-compatible embedding 调用失败：{exc}",
                status_code=500,
            ) from exc

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
