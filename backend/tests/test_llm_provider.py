from __future__ import annotations

import asyncio

import pytest

from app.llm.adapters.base import BaseLLMProvider
from app.llm.adapters.mock_provider import MockLLMProvider
from app.llm.embedding import (
    BaseEmbeddingProvider,
    FallbackEmbeddingProvider,
    MockEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
    get_embedding_provider,
)
from app.llm.provider import FallbackLLMProvider, LoggingLLMProvider, get_llm_provider
from app.llm.schemas import ChatMessage, ChatResponse


def test_mock_chat_returns_data_structure_content() -> None:
    asyncio.run(_test_mock_chat_returns_data_structure_content())


async def _test_mock_chat_returns_data_structure_content() -> None:
    provider = MockLLMProvider()

    response = await provider.chat(
        [ChatMessage(role="user", content="请解释数据结构里的栈与队列")]
    )

    assert "栈" in response.content
    assert "队列" in response.content
    assert response.provider == "mock"
    assert response.total_tokens > 0


def test_mock_stream_chat_yields_chunks() -> None:
    asyncio.run(_test_mock_stream_chat_yields_chunks())


async def _test_mock_stream_chat_yields_chunks() -> None:
    provider = MockLLMProvider()

    chunks = [
        chunk
        async for chunk in provider.stream_chat(
            [ChatMessage(role="user", content="请总结二叉树遍历")]
        )
    ]

    assert chunks
    assert "二叉树" in "".join(chunks)


def test_mock_resource_generation_contains_required_sections() -> None:
    asyncio.run(_test_mock_resource_generation_contains_required_sections())


async def _test_mock_resource_generation_contains_required_sections() -> None:
    provider = MockLLMProvider()

    response = await provider.chat(
        [ChatMessage(role="user", content="请为学生生成个性化学习资源\n资源类型：讲解\n知识点：栈与队列")]
    )

    assert "个性化原因" in response.content
    assert "引用来源" in response.content
    assert "栈与队列" in response.content


def test_mock_embedding_is_stable_and_distinguishes_texts() -> None:
    asyncio.run(_test_mock_embedding_is_stable_and_distinguishes_texts())


async def _test_mock_embedding_is_stable_and_distinguishes_texts() -> None:
    provider = MockLLMProvider()

    first = await provider.embedding(["栈", "队列"])
    second = await provider.embedding(["栈"])

    assert len(first.embeddings) == 2
    assert len(first.embeddings[0]) == 1024
    assert first.embeddings[0] == second.embeddings[0]
    assert first.embeddings[0] != first.embeddings[1]


def test_embedding_provider_prefers_embedding_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    import app.llm.embedding as embedding_module

    monkeypatch.setattr(
        embedding_module,
        "settings",
        SimpleNamespace(
            embedding_provider="openai_compatible",
            embedding_api_key="embedding-key",
            embedding_base_url="https://embedding.example/v1",
            llm_api_key="llm-key",
            llm_base_url="https://llm.example/v1",
            embedding_model="text-embedding-test",
            embedding_dimension=1024,
        ),
    )

    provider = get_embedding_provider()

    assert isinstance(provider, FallbackEmbeddingProvider)
    assert isinstance(provider.primary, OpenAICompatibleEmbeddingProvider)
    assert provider.primary._api_key == "embedding-key"
    assert provider.primary._base_url == "https://embedding.example/v1"


def test_embedding_provider_uses_mock_without_any_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    import app.llm.embedding as embedding_module

    monkeypatch.setattr(
        embedding_module,
        "settings",
        SimpleNamespace(
            embedding_provider="openai_compatible",
            embedding_api_key="",
            embedding_base_url="",
            llm_api_key="",
            llm_base_url="",
            embedding_model="text-embedding-test",
            embedding_dimension=1024,
        ),
    )

    provider = get_embedding_provider()

    assert isinstance(provider, MockEmbeddingProvider)


def test_embedding_provider_keeps_legacy_llm_key_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    import app.llm.embedding as embedding_module

    monkeypatch.setattr(
        embedding_module,
        "settings",
        SimpleNamespace(
            embedding_provider="openai_compatible",
            embedding_api_key="",
            embedding_base_url="",
            llm_api_key="legacy-llm-key",
            llm_base_url="https://legacy.example/v1",
            embedding_model="text-embedding-test",
            embedding_dimension=1024,
        ),
    )

    provider = get_embedding_provider()

    assert isinstance(provider, FallbackEmbeddingProvider)
    assert isinstance(provider.primary, OpenAICompatibleEmbeddingProvider)
    assert provider.primary._api_key == "legacy-llm-key"
    assert provider.primary._base_url == "https://legacy.example/v1"


def test_compatible_without_api_key_falls_back_to_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    import app.llm.provider as provider_module

    monkeypatch.setattr(
        provider_module,
        "settings",
        SimpleNamespace(
            llm_provider="compatible",
            llm_api_key="",
            llm_base_url="",
            llm_model_name="mock-learning-model",
            llm_timeout_seconds=60,
            embedding_model="mock-embedding",
            embedding_dimension=1024,
        ),
    )

    provider = get_llm_provider()

    assert isinstance(provider, MockLLMProvider)


class FakeDB:
    def __init__(self) -> None:
        self.items: list[object] = []

    def add(self, item: object) -> None:
        self.items.append(item)

    async def flush(self) -> None:
        return None


class FailingProvider(BaseLLMProvider):
    provider_name = "failing"

    async def chat(self, *args, **kwargs) -> ChatResponse:
        raise RuntimeError("Authorization: Bearer should-not-leak")

    async def stream_chat(self, *args, **kwargs):
        raise RuntimeError("stream failed")
        yield ""

    async def embedding(self, *args, **kwargs):
        raise RuntimeError("embedding failed")


def test_logging_provider_records_failed_calls_safely() -> None:
    asyncio.run(_test_logging_provider_records_failed_calls_safely())


async def _test_logging_provider_records_failed_calls_safely() -> None:
    db = FakeDB()
    provider = LoggingLLMProvider(FailingProvider(), db=db)  # type: ignore[arg-type]

    with pytest.raises(Exception):
        await provider.chat([ChatMessage(role="user", content="测试")])

    assert len(db.items) == 1
    log = db.items[0]
    assert getattr(log, "status") == "failed"
    assert "should-not-leak" not in str(getattr(log, "error_message"))


def test_llm_fallback_provider_uses_mock_when_primary_fails() -> None:
    asyncio.run(_test_llm_fallback_provider_uses_mock_when_primary_fails())


async def _test_llm_fallback_provider_uses_mock_when_primary_fails() -> None:
    provider = FallbackLLMProvider(FailingProvider(), MockLLMProvider())

    response = await provider.chat([ChatMessage(role="user", content="请解释栈与队列")])

    assert response.provider == "mock"
    assert response.raw["fallback_used"] is True
    assert "栈" in response.content


class FailingEmbeddingProvider(BaseEmbeddingProvider):
    @property
    def dimension(self) -> int:
        return 1024

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding failed")


def test_embedding_fallback_provider_uses_mock_vectors() -> None:
    asyncio.run(_test_embedding_fallback_provider_uses_mock_vectors())


async def _test_embedding_fallback_provider_uses_mock_vectors() -> None:
    provider = FallbackEmbeddingProvider(
        FailingEmbeddingProvider(),
        MockEmbeddingProvider(1024),
    )

    vectors = await provider.embed_texts(["栈", "队列"])

    assert len(vectors) == 2
    assert len(vectors[0]) == 1024
    assert vectors[0] != vectors[1]
