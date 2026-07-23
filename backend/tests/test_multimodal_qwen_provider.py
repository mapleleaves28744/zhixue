from __future__ import annotations

import httpx
import pytest

from app.llm.multimodal_provider import QwenImageProvider, build_multimodal_provider
from app.services.multimodal_resource_service import MultimodalResourceService


def test_qwen_image_provider_is_selected_when_configured(monkeypatch) -> None:
    monkeypatch.setattr("app.llm.multimodal_provider.settings.multimodal_provider", "qwen_image")
    monkeypatch.setattr("app.llm.multimodal_provider.settings.qwen_image_api_key", "local-test-key")

    provider = build_multimodal_provider()

    assert isinstance(provider, QwenImageProvider)
    assert provider.provider_name == "qwen_image"


def test_qwen_keeps_a_natural_requirement_as_the_image_prompt() -> None:
    service = object.__new__(MultimodalResourceService)
    service.provider = QwenImageProvider()
    requirement = "生成一张讲解队列知识的课程插图，适合大学数据结构课堂视频。"

    prompt = service._image_prompt(
        topic="队列",
        image_type="concept_illustration",
        style="扁平教学图",
        requirement=requirement,
        brief={"source_summary": "队列是先进先出的线性表。", "style_hint": "分步讲解"},
    )

    assert prompt == requirement


@pytest.mark.asyncio
async def test_qwen_image_request_keeps_prompt_and_enables_official_extension(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def __init__(self, payload: dict[str, object] | None = None, content: bytes = b"") -> None:
            self._payload = payload or {}
            self.content = content
            self.headers = {"content-type": "image/png"}
            self.status_code = 200
            self.text = ""
            self.is_error = False

        def json(self) -> dict[str, object]:
            return self._payload

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def post(self, url: str, *, headers: dict[str, str], json: dict[str, object]) -> FakeResponse:
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = json
            return FakeResponse(
                {
                    "output": {
                        "choices": [
                            {"message": {"content": [{"image": "https://image.example/generated.png"}]}}
                        ]
                    }
                }
            )

        async def get(self, url: str) -> FakeResponse:
            captured["image_url"] = url
            return FakeResponse(content=b"qwen-image-bytes")

    monkeypatch.setattr("app.llm.multimodal_provider.httpx.AsyncClient", lambda **_: FakeClient())
    monkeypatch.setattr("app.llm.multimodal_provider.settings.qwen_image_api_key", "local-test-key")
    monkeypatch.setattr("app.llm.multimodal_provider.settings.qwen_image_model", "qwen-test-model")
    monkeypatch.setattr("app.llm.multimodal_provider.settings.qwen_image_base_url", "https://api.example/generation")
    monkeypatch.setattr("app.llm.multimodal_provider.settings.qwen_image_prompt_extend", True)

    prompt = "生成一张讲解队列知识的课程插图，适合大学数据结构课堂视频。"
    result = await QwenImageProvider().generate_image(prompt=prompt, size="1280x720", style="不应拼接到提示词")

    assert result.image_bytes == b"qwen-image-bytes"
    assert result.provider == "qwen_image"
    assert captured["image_url"] == "https://image.example/generated.png"
    assert captured["payload"] == {
        "model": "qwen-test-model",
        "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]},
        "parameters": {"prompt_extend": True, "watermark": False, "size": "1280*720"},
    }
