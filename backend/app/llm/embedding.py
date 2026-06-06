from __future__ import annotations

import hashlib
import math
import os
import struct
from abc import ABC, abstractmethod

from app.core.config import settings


class BaseEmbeddingProvider(ABC):
    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        ...


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic mock: same text always produces the same vector."""

    def __init__(self, dimension: int = 1024) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

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
                json={"model": self._model, "input": texts, "dimensions": self._dimension},
            )
            resp.raise_for_status()
            data = resp.json()
        # Sort by index to guarantee ordering
        sorted_items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_items]


class SentenceTransformerEmbeddingProvider(BaseEmbeddingProvider):
    """Local real embedding provider backed by sentence-transformers."""

    def __init__(self, model_name: str, dimension: int = 1024) -> None:
        self.model_name = model_name
        self._dimension = dimension
        self._model = None

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        model = self._load_model()
        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        result = [vector.tolist() for vector in vectors]
        for vector in result:
            if len(vector) != self._dimension:
                raise RuntimeError(
                    f"Embedding dimension mismatch: expected {self._dimension}, got {len(vector)}"
                )
        return result

    def _load_model(self):
        if self._model is None:
            os.environ.setdefault("USE_TF", "0")
            os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
            os.environ.setdefault("TRANSFORMERS_NO_FLAX", "1")
            os.environ.setdefault("TRANSFORMERS_NO_TORCHVISION", "1")
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "sentence-transformers is required for EMBEDDING_PROVIDER=sentence_transformers"
                ) from exc
            self._model = SentenceTransformer(self.model_name)
        return self._model


class FallbackEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, primary: BaseEmbeddingProvider, fallback: BaseEmbeddingProvider) -> None:
        self.primary = primary
        self.fallback = fallback

    @property
    def dimension(self) -> int:
        return self.primary.dimension

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        try:
            return await self.primary.embed_texts(texts)
        except Exception:
            return await self.fallback.embed_texts(texts)


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
    provider = settings.embedding_provider.lower().replace("-", "_")
    if provider == "mock":
        return MockEmbeddingProvider(settings.embedding_dimension)
    if provider in ("sentence_transformers", "sentence_transformer", "local_bge"):
        return SentenceTransformerEmbeddingProvider(
            model_name=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )
    if provider in ("openai", "compatible", "openai_compatible"):
        api_key = settings.embedding_api_key or settings.llm_api_key
        base_url = (
            settings.embedding_base_url
            or settings.llm_base_url
            or "https://api.openai.com/v1"
        )
        if not api_key:
            if not settings.embedding_allow_mock_fallback:
                raise RuntimeError(
                    "Real embedding provider is required, but no EMBEDDING_API_KEY/LLM_API_KEY is configured."
                )
            return MockEmbeddingProvider(settings.embedding_dimension)
        primary = OpenAICompatibleEmbeddingProvider(
            api_key=api_key,
            base_url=base_url,
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )
        if not settings.embedding_allow_mock_fallback:
            return primary
        return FallbackEmbeddingProvider(primary, MockEmbeddingProvider(settings.embedding_dimension))
    return MockEmbeddingProvider(settings.embedding_dimension)
