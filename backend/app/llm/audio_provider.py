from __future__ import annotations

import base64
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

MIMO_ASR_MODEL = "mimo-v2.5-asr"
MIMO_TTS_MODEL = "mimo-v2.5-tts"
MIMO_TTS_VOICECLONE_MODEL = "mimo-v2.5-tts-voiceclone"
MIMO_TTS_VOICEDESIGN_MODEL = "mimo-v2.5-tts-voicedesign"


@dataclass
class ASRResult:
    text: str
    duration_ms: int = 0
    language: str = "zh"
    model: str = "mock-asr"
    provider: str = "mock_audio"
    raw: dict[str, object] | None = None


@dataclass
class TTSResult:
    audio_base64: str
    duration_ms: int = 0
    format: str = "wav"
    model: str = "mock-tts"
    provider: str = "mock_audio"
    raw: dict[str, object] | None = None


class BaseAudioProvider(ABC):
    provider_name = "base_audio"

    @abstractmethod
    async def transcribe(
        self,
        audio_base64: str,
        *,
        filename: str = "audio.wav",
        language: str = "zh",
    ) -> ASRResult:
        ...

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        speed: float = 1.0,
        response_format: str = "wav",
        model: str | None = None,
    ) -> TTSResult:
        ...


class MockAudioProvider(BaseAudioProvider):
    provider_name = "mock_audio"

    async def transcribe(
        self,
        audio_base64: str,
        *,
        filename: str = "audio.wav",
        language: str = "zh",
    ) -> ASRResult:
        byte_count = _safe_audio_byte_count(audio_base64)
        return ASRResult(
            text=f"这是 Mock 语音识别结果：学生通过 {filename} 提问，请围绕数据结构课程进行讲解。",
            duration_ms=max(1, byte_count // 32),
            language=language,
            model="mock-asr",
            provider=self.provider_name,
        )

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        speed: float = 1.0,
        response_format: str = "wav",
        model: str | None = None,
    ) -> TTSResult:
        placeholder = f"MOCK_AUDIO:{response_format}:{speed}:{voice or 'default'}:{text[:120]}"
        return TTSResult(
            audio_base64=base64.b64encode(placeholder.encode("utf-8")).decode("utf-8"),
            duration_ms=max(1, len(text) * 20),
            format=response_format,
            model=model or "mock-tts",
            provider=self.provider_name,
        )


class FallbackAudioProvider(BaseAudioProvider):
    provider_name = "fallback_audio"

    def __init__(self, primary: BaseAudioProvider, fallback: BaseAudioProvider) -> None:
        self.primary = primary
        self.fallback = fallback

    async def transcribe(
        self,
        audio_base64: str,
        *,
        filename: str = "audio.wav",
        language: str = "zh",
    ) -> ASRResult:
        try:
            result = await self.primary.transcribe(audio_base64, filename=filename, language=language)
            result.raw = {**(result.raw or {}), "fallback_used": False}
            return result
        except Exception as exc:
            logger.warning("Audio ASR provider %s failed, falling back to mock: %s", self.primary.provider_name, exc)
            result = await self.fallback.transcribe(audio_base64, filename=filename, language=language)
            result.raw = {
                **(result.raw or {}),
                "fallback_used": True,
                "failed_provider": self.primary.provider_name,
                "fallback_reason": str(exc)[:300],
            }
            return result

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        speed: float = 1.0,
        response_format: str = "wav",
        model: str | None = None,
    ) -> TTSResult:
        try:
            result = await self.primary.synthesize(
                text,
                voice=voice,
                speed=speed,
                response_format=response_format,
                model=model,
            )
            result.raw = {**(result.raw or {}), "fallback_used": False}
            return result
        except Exception as exc:
            logger.warning("Audio TTS provider %s failed, falling back to mock: %s", self.primary.provider_name, exc)
            result = await self.fallback.synthesize(
                text,
                voice=voice,
                speed=speed,
                response_format=response_format,
                model=model,
            )
            result.raw = {
                **(result.raw or {}),
                "fallback_used": True,
                "failed_provider": self.primary.provider_name,
                "fallback_reason": str(exc)[:300],
            }
            return result


class MiMoTokenPlanAudioProvider(BaseAudioProvider):
    provider_name = "xiaomi_mimo_audio"

    def __init__(self) -> None:
        self._api_key = settings.llm_api_key
        self._base_url = (settings.llm_base_url or "https://api.xiaomimimo.com/v1").rstrip("/")

    async def transcribe(
        self,
        audio_base64: str,
        *,
        filename: str = "audio.wav",
        language: str = "zh",
    ) -> ASRResult:
        audio_bytes = base64.b64decode(audio_base64)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self._base_url}/audio/transcriptions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                files={"file": (filename, audio_bytes, _content_type(filename))},
                data={"model": MIMO_ASR_MODEL, "language": language},
            )
            response.raise_for_status()
            payload = response.json()
        return ASRResult(
            text=str(payload.get("text") or ""),
            duration_ms=int(payload.get("duration_ms") or payload.get("duration") or 0),
            language=str(payload.get("language") or language),
            model=MIMO_ASR_MODEL,
            provider=self.provider_name,
        )

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        speed: float = 1.0,
        response_format: str = "wav",
        model: str | None = None,
    ) -> TTSResult:
        selected_model = model if model in _tts_models() else MIMO_TTS_MODEL
        payload: dict[str, object] = {
            "model": selected_model,
            "input": text,
            "response_format": response_format,
            "speed": speed,
        }
        if voice:
            payload["voice"] = voice
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self._base_url}/audio/speech",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            audio_bytes = response.content
        return TTSResult(
            audio_base64=base64.b64encode(audio_bytes).decode("utf-8"),
            format=response_format,
            model=selected_model,
            provider=self.provider_name,
        )


def build_audio_provider() -> BaseAudioProvider:
    if settings.llm_api_key and settings.llm_base_url:
        return FallbackAudioProvider(
            primary=MiMoTokenPlanAudioProvider(),
            fallback=MockAudioProvider(),
        )
    return MockAudioProvider()


def _safe_audio_byte_count(audio_base64: str) -> int:
    if not audio_base64:
        return 0
    padding = "=" * (-len(audio_base64) % 4)
    return len(base64.b64decode(audio_base64 + padding))


def _content_type(filename: str) -> str:
    lowered = filename.lower()
    if lowered.endswith(".mp3"):
        return "audio/mpeg"
    if lowered.endswith(".m4a"):
        return "audio/mp4"
    if lowered.endswith(".webm"):
        return "audio/webm"
    return "audio/wav"


def _tts_models() -> set[str]:
    return {MIMO_TTS_MODEL, MIMO_TTS_VOICECLONE_MODEL, MIMO_TTS_VOICEDESIGN_MODEL}
