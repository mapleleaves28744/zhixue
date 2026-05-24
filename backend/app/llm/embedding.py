from __future__ import annotations

import hashlib
import math
import struct
from abc import ABC, abstractmethod


class BaseEmbeddingProvider(ABC):
    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        ...


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic mock: same text always produces the same 1024-d vector."""

    @property
    def dimension(self) -> int:
        return 1024

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [_text_to_vec(text, self.dimension) for text in texts]


class OpenAICompatibleEmbeddingProvider(BaseEmbeddingProvider):
    """Placeholder for real embedding API (OpenAI / compatible)."""

    def __init__(self, api_key: str, base_url: str, model: str, dimension: int = 1024) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        import httpx

        url = f"{self._base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                url,
                headers=headers,
                json={"model": self._model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
        # Sort by index to guarantee ordering
        sorted_items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_items]


def _text_to_vec(text: str, dim: int) -> list[float]:
    """Convert text to a deterministic pseudo-random vector of *dim* floats."""
    h = hashlib.sha256(text.encode("utf-8")).digest()
    # Repeat hash bytes to fill dim * 4 bytes (float32 = 4 bytes)
    needed = dim * 4
    buf = (h * (needed // len(h) + 1))[:needed]
    floats = list(struct.unpack(f"{dim}f", buf))
    floats = [0.0 if not math.isfinite(f) else f for f in floats]
    # Normalize to unit vector for cosine similarity
    norm = sum(f * f for f in floats) ** 0.5
    if norm > 0:
        floats = [f / norm for f in floats]
    return floats


def get_embedding_provider() -> BaseEmbeddingProvider:
    from app.core.config import settings

    provider = settings.embedding_provider.lower()
    if provider == "mock":
        return MockEmbeddingProvider()
    if provider in ("openai", "compatible"):
        if not settings.llm_api_key:
            return MockEmbeddingProvider()
        return OpenAICompatibleEmbeddingProvider(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url or "https://api.openai.com/v1",
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )
    return MockEmbeddingProvider()
