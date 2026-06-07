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


def test_audio_api_routes_are_registered() -> None:
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
