from __future__ import annotations

import asyncio

import pytest

from app.core.exceptions import BusinessException
from app.llm.adapters.base import BaseLLMProvider
from app.llm.adapters.mock_provider import MockLLMProvider
from app.llm.adapters.openai_compatible import OpenAICompatibleLLMProvider
from app.llm.embedding import (
    BaseEmbeddingProvider,
    FallbackEmbeddingProvider,
    MockEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
    get_embedding_provider,
)
from app.llm.provider import FallbackLLMProvider, LoggingLLMProvider, get_llm_provider
from app.llm.schemas import ChatMessage, ChatResponse, ToolCall


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
            embedding_allow_mock_fallback=True,
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
            embedding_allow_mock_fallback=True,
        ),
    )

    provider = get_embedding_provider()

    assert isinstance(provider, MockEmbeddingProvider)


def test_embedding_provider_requires_real_key_when_mock_fallback_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
            embedding_model="text-embedding-3-small",
            embedding_dimension=1024,
            embedding_allow_mock_fallback=False,
        ),
    )

    with pytest.raises(RuntimeError, match="Real embedding provider is required"):
        get_embedding_provider()


def test_embedding_provider_supports_local_sentence_transformer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    import app.llm.embedding as embedding_module

    monkeypatch.setattr(
        embedding_module,
        "settings",
        SimpleNamespace(
            embedding_provider="sentence_transformers",
            embedding_api_key="",
            embedding_base_url="",
            llm_api_key="",
            llm_base_url="",
            embedding_model="BAAI/bge-large-zh-v1.5",
            embedding_dimension=1024,
            embedding_allow_mock_fallback=False,
        ),
    )

    provider = get_embedding_provider()

    assert isinstance(provider, embedding_module.SentenceTransformerEmbeddingProvider)
    assert provider.dimension == 1024
    assert provider.model_name == "BAAI/bge-large-zh-v1.5"


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
            embedding_allow_mock_fallback=True,
        ),
    )

    provider = get_embedding_provider()

    assert isinstance(provider, FallbackEmbeddingProvider)
    assert isinstance(provider.primary, OpenAICompatibleEmbeddingProvider)
    assert provider.primary._api_key == "legacy-llm-key"
    assert provider.primary._base_url == "https://legacy.example/v1"


def test_standalone_openai_embedding_request_sends_configured_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_test_standalone_openai_embedding_request_sends_configured_dimensions(monkeypatch))


async def _test_standalone_openai_embedding_request_sends_configured_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"data": [{"index": 0, "embedding": [0.1] * 1024}]}

    class FakeClient:
        def __init__(self, timeout: int) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, *, headers: dict[str, str], json: dict[str, object]):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    provider = OpenAICompatibleEmbeddingProvider(
        api_key="test-key",
        base_url="https://embedding.example/v1",
        model="text-embedding-3-small",
        dimension=1024,
    )

    vectors = await provider.embed_texts(["栈与队列"])

    assert len(vectors[0]) == 1024
    assert captured["json"] == {
        "model": "text-embedding-3-small",
        "input": ["栈与队列"],
        "dimensions": 1024,
    }


def test_llm_openai_embedding_request_sends_configured_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_test_llm_openai_embedding_request_sends_configured_dimensions(monkeypatch))


async def _test_llm_openai_embedding_request_sends_configured_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "data": [{"index": 0, "embedding": [0.2] * 1024}],
                "model": "text-embedding-3-small",
                "usage": {"prompt_tokens": 3, "total_tokens": 3},
            }

    class FakeClient:
        def __init__(self, timeout: int) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, *, headers: dict[str, str], json: dict[str, object]):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    provider = OpenAICompatibleLLMProvider(
        api_key="test-key",
        base_url="https://api.example/v1",
        model="chat-model",
        embedding_model="text-embedding-3-small",
        embedding_dimension=1024,
    )

    response = await provider.embedding(["哈希表"])

    assert len(response.embeddings[0]) == 1024
    assert captured["json"] == {
        "model": "text-embedding-3-small",
        "input": ["哈希表"],
        "dimensions": 1024,
    }


def test_openai_chat_supports_native_tool_calls_and_mimo_reasoning_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_test_openai_chat_supports_native_tool_calls_and_mimo_reasoning_history(monkeypatch))


async def _test_openai_chat_supports_native_tool_calls_and_mimo_reasoning_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "model": "mimo-v2.5",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "reasoning_content": "private-protocol-state",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "search_course_knowledge",
                                        "arguments": "{\"query\":\"栈\"}",
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }

    class FakeClient:
        def __init__(self, timeout: int) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, *, headers: dict[str, str], json: dict[str, object]):
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    provider = OpenAICompatibleLLMProvider(
        api_key="test-key",
        base_url="https://token-plan-cn.xiaomimimo.com/v1",
        model="mimo-v2.5",
    )

    response = await provider.chat(
        [
            ChatMessage(
                role="assistant",
                content="",
                reasoning_content="previous-private-state",
                tool_calls=[
                    ToolCall(
                        id="previous_call",
                        name="search_course_knowledge",
                        arguments={"query": "队列"},
                    )
                ],
            ),
            ChatMessage(role="tool", content='{"items":[]}', tool_call_id="previous_call"),
            ChatMessage(role="user", content="继续分析栈"),
        ],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "search_course_knowledge",
                    "description": "检索课程知识库",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
        tool_choice="auto",
        response_format={"type": "json_object"},
    )

    request_payload = captured["json"]
    assert request_payload["tools"][0]["function"]["name"] == "search_course_knowledge"
    assert request_payload["tool_choice"] == "auto"
    assert request_payload["response_format"] == {"type": "json_object"}
    assert request_payload["messages"][0]["reasoning_content"] == "previous-private-state"
    assert request_payload["messages"][1]["tool_call_id"] == "previous_call"
    assert response.finish_reason == "tool_calls"
    assert response.reasoning_content == "private-protocol-state"
    assert response.tool_calls[0].name == "search_course_knowledge"
    assert response.tool_calls[0].arguments == {"query": "栈"}


def test_llm_provider_can_disable_mock_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    import app.llm.provider as provider_module

    monkeypatch.setattr(
        provider_module,
        "settings",
        SimpleNamespace(
            llm_provider="compatible",
            llm_api_key="real-key",
            llm_base_url="https://api.example/v1",
            llm_model_name="real-model",
            llm_timeout_seconds=60,
            embedding_model="mock-embedding",
            embedding_dimension=1024,
        ),
    )

    provider = provider_module.get_llm_provider(allow_mock_fallback=False)

    assert isinstance(provider, OpenAICompatibleLLMProvider)


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


class PartialThenFailProvider(BaseLLMProvider):
    provider_name = "partial-primary"

    async def chat(self, *args, **kwargs) -> ChatResponse:
        raise NotImplementedError

    async def stream_chat(self, *args, **kwargs):
        yield "主模型已输出"
        raise RuntimeError("stream failed after first token")

    async def embedding(self, *args, **kwargs):
        raise NotImplementedError


class RecordingStreamProvider(BaseLLMProvider):
    provider_name = "recording-fallback"

    def __init__(self) -> None:
        self.stream_calls = 0

    async def chat(self, *args, **kwargs) -> ChatResponse:
        raise NotImplementedError

    async def stream_chat(self, *args, **kwargs):
        self.stream_calls += 1
        yield "回退回答"

    async def embedding(self, *args, **kwargs):
        raise NotImplementedError


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


class FallbackNamedProvider(BaseLLMProvider):
    provider_name = "fallback"

    async def chat(self, *args, **kwargs) -> ChatResponse:
        return ChatResponse(content="真实回答", provider="xiaomi_mimo", model="mimo-v2.5")

    async def stream_chat(self, *args, **kwargs):
        yield "真实回答"

    async def embedding(self, *args, **kwargs):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_logging_provider_records_the_provider_that_actually_answered() -> None:
    db = FakeDB()
    provider = LoggingLLMProvider(FallbackNamedProvider(), db=db)  # type: ignore[arg-type]

    await provider.chat([ChatMessage(role="user", content="测试")])

    assert getattr(db.items[0], "provider") == "xiaomi_mimo"


def test_llm_fallback_provider_uses_mock_when_primary_fails() -> None:
    asyncio.run(_test_llm_fallback_provider_uses_mock_when_primary_fails())


async def _test_llm_fallback_provider_uses_mock_when_primary_fails() -> None:
    provider = FallbackLLMProvider(FailingProvider(), MockLLMProvider())

    response = await provider.chat([ChatMessage(role="user", content="请解释栈与队列")])

    assert response.provider == "mock"
    assert response.raw["fallback_used"] is True
    assert "栈" in response.content


@pytest.mark.asyncio
async def test_stream_fallback_is_allowed_before_first_token() -> None:
    fallback = RecordingStreamProvider()
    inner = FallbackLLMProvider(FailingProvider(), fallback)
    provider = LoggingLLMProvider(inner, db=FakeDB())  # type: ignore[arg-type]

    chunks = [chunk async for chunk in provider.stream_chat([ChatMessage(role="user", content="栈")])]

    assert chunks == ["回退回答"]
    assert fallback.stream_calls == 1
    assert inner.last_stream_fallback_used is True
    assert inner.last_stream_failed_provider == "failing"
    assert inner.last_stream_provider_name == "recording-fallback"
    assert getattr(provider.db.items[0], "provider") == "recording-fallback"


@pytest.mark.asyncio
async def test_stream_fallback_is_forbidden_after_first_token() -> None:
    fallback = RecordingStreamProvider()
    inner = FallbackLLMProvider(PartialThenFailProvider(), fallback)
    db = FakeDB()
    provider = LoggingLLMProvider(inner, db=db)  # type: ignore[arg-type]
    chunks: list[str] = []

    with pytest.raises(BusinessException) as exc_info:
        async for chunk in provider.stream_chat([ChatMessage(role="user", content="栈")]):
            chunks.append(chunk)

    assert chunks == ["主模型已输出"]
    assert exc_info.value.detail == "stream failed after first token"
    assert fallback.stream_calls == 0
    assert inner.last_stream_fallback_used is False
    assert getattr(db.items[0], "status") == "failed"


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
