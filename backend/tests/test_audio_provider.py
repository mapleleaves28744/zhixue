from __future__ import annotations

import asyncio
import base64
from types import SimpleNamespace
from uuid import uuid4

import pytest


def test_mock_audio_provider_transcribes_and_synthesizes_without_real_key() -> None:
    asyncio.run(_test_mock_audio_provider_transcribes_and_synthesizes_without_real_key())


async def _test_mock_audio_provider_transcribes_and_synthesizes_without_real_key() -> None:
    from app.llm.audio_provider import MockAudioProvider

    provider = MockAudioProvider()
    audio_base64 = base64.b64encode(b"fake-audio").decode("ascii")

    asr = await provider.transcribe(audio_base64, filename="question.wav")
    tts = await provider.synthesize("栈是后进先出。", response_format="mp3")

    assert asr.provider == "mock_audio"
    assert "question.wav" in asr.text
    assert tts.provider == "mock_audio"
    assert tts.format == "mp3"
    assert tts.audio_base64


def test_fallback_audio_provider_marks_failed_primary() -> None:
    asyncio.run(_test_fallback_audio_provider_marks_failed_primary())


async def _test_fallback_audio_provider_marks_failed_primary() -> None:
    from app.llm.audio_provider import FallbackAudioProvider, MockAudioProvider

    class FailedProvider(MockAudioProvider):
        provider_name = "xiaomi_mimo_audio"

        async def transcribe(self, *args, **kwargs):
            raise RuntimeError("network timeout")

    result = await FallbackAudioProvider(FailedProvider(), MockAudioProvider()).transcribe(
        base64.b64encode(b"fake-audio").decode("ascii"),
        filename="question.wav",
    )

    assert result.provider == "mock_audio"
    assert result.raw["fallback_used"] is True
    assert result.raw["failed_provider"] == "xiaomi_mimo_audio"
    assert "network timeout" in result.raw["fallback_reason"]


def test_audio_tools_are_registered_and_do_not_require_db_writes() -> None:
    from app.agent_runtime.service_tools import build_learning_tool_registry

    registry = build_learning_tool_registry(SimpleNamespace(), SimpleNamespace(id=uuid4(), role="student"))  # type: ignore[arg-type]
    schemas = {item["function"]["name"]: item["function"]["parameters"] for item in registry.tool_schemas()}

    assert schemas["transcribe_audio"]["required"] == ["audio_base64"]
    assert schemas["synthesize_speech"]["required"] == ["text"]
    assert registry.get("transcribe_audio").writes_db is False
    assert registry.get("synthesize_speech").writes_db is False


@pytest.mark.asyncio
async def test_mimo_audio_provider_uses_chat_completions_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.llm import audio_provider as module

    captured: list[tuple[str, dict[str, object]]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            url = captured[-1][0]
            if url.endswith("/chat/completions") and captured[-1][1].get("model") == module.MIMO_ASR_MODEL:
                return {
                    "choices": [{"message": {"content": "识别结果"}}],
                    "usage": {"seconds": 2},
                }
            return {
                "choices": [
                    {
                        "message": {
                            "audio": {
                                "data": base64.b64encode(b"RIFFwav").decode("ascii"),
                                "transcript": "hello",
                            }
                        }
                    }
                ],
                "usage": {},
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url: str, *, headers: dict[str, str], json: dict[str, object]):
            captured.append((url, json))
            return FakeResponse()

    monkeypatch.setattr(module.settings, "llm_api_key", "test-key")
    monkeypatch.setattr(module.settings, "llm_base_url", "https://token-plan-cn.xiaomimimo.com/v1")
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: FakeClient())

    provider = module.MiMoTokenPlanAudioProvider()
    asr = await provider.transcribe(base64.b64encode(b"wav").decode("ascii"), filename="clip.wav")
    tts = await provider.synthesize("栈是后进先出。", response_format="wav")

    assert asr.text == "识别结果"
    assert tts.provider == "xiaomi_mimo_audio"
    assert all("/chat/completions" in url for url, _ in captured)
    assert captured[0][1]["model"] == module.MIMO_ASR_MODEL
    assert captured[1][1]["model"] == module.MIMO_TTS_MODEL
    asr_message = captured[0][1]["messages"][0]
    assert asr_message["content"][0]["input_audio"]["data"].startswith("data:audio/wav;base64,")
    from app.main import app

    paths = app.openapi()["paths"]

    assert "/api/v1/audio/transcribe" in paths
    assert "/api/v1/audio/synthesize" in paths


@pytest.mark.asyncio
async def test_transcribe_audio_tool_output_does_not_echo_input_base64() -> None:
    from app.agent_runtime.service_tools import build_learning_tool_registry
    from app.agent_runtime.tools import ToolContext

    audio_base64 = base64.b64encode(b"fake-audio").decode("ascii")
    registry = build_learning_tool_registry(SimpleNamespace(), SimpleNamespace(id=uuid4(), role="student"))  # type: ignore[arg-type]
    result = await registry.execute(
        "transcribe_audio",
        {"audio_base64": audio_base64, "filename": "question.wav"},
        ToolContext(task_id=uuid4(), tool_call_id="asr", user_id=uuid4(), course_id=uuid4()),
    )

    assert result.success is True
    assert result.output["provider"] == "mock_audio"
    assert result.output["audio_bytes"] == len(b"fake-audio")
    assert audio_base64 not in str(result.output)
    assert audio_base64 not in str(result.evidence)
