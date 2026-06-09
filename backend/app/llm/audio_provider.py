from __future__ import annotations

import base64
import logging
import struct
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
        duration_ms = max(200, int(len(text) * 20 / max(speed, 0.5)))
        audio_format = response_format if response_format in {"wav", "mp3", "pcm16"} else "wav"
        wav_bytes = _mock_silent_wav(duration_ms=duration_ms)
        return TTSResult(
            audio_base64=base64.b64encode(wav_bytes).decode("ascii"),
            duration_ms=duration_ms,
            format=audio_format if audio_format != "pcm16" else "wav",
            model=model or "mock-tts",
            provider=self.provider_name,
            raw={"mock": True, "text_preview": text[:120]},
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

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "api-key": self._api_key,
            "Content-Type": "application/json",
        }

    async def transcribe(
        self,
        audio_base64: str,
        *,
        filename: str = "audio.wav",
        language: str = "zh",
    ) -> ASRResult:
        audio_bytes = base64.b64decode(audio_base64)
        mime = _content_type(filename)
        data_url = f"data:{mime};base64,{base64.b64encode(audio_bytes).decode('utf-8')}"
        payload = {
            "model": MIMO_ASR_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": data_url,
                                "format": _asr_format(filename),
                            },
                        }
                    ],
                }
            ],
        }
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        message = (body.get("choices") or [{}])[0].get("message") or {}
        usage = body.get("usage") or {}
        seconds = usage.get("seconds")
        duration_ms = int(seconds * 1000) if isinstance(seconds, (int, float)) else 0
        return ASRResult(
            text=str(message.get("content") or ""),
            duration_ms=duration_ms,
            language=language,
            model=MIMO_ASR_MODEL,
            provider=self.provider_name,
            raw={"usage": usage},
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
        selected_voice = voice or _default_voice(text, selected_model)
        audio_format = response_format if response_format in {"wav", "pcm16"} else "wav"
        messages = _build_tts_messages(text, selected_model, speed=speed, voice=selected_voice)
        audio_payload: dict[str, str] = {
            "format": audio_format,
            "voice": selected_voice,
        }
        payload: dict[str, object] = {
            "model": selected_model,
            "messages": messages,
            "audio": audio_payload,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        message = (body.get("choices") or [{}])[0].get("message") or {}
        audio = message.get("audio") or {}
        audio_b64 = str(audio.get("data") or "")
        if not audio_b64:
            raise RuntimeError("MiMo TTS 响应缺少 audio.data")
        return TTSResult(
            audio_base64=audio_b64,
            format=audio_format,
            model=selected_model,
            provider=self.provider_name,
            raw={"transcript": audio.get("transcript"), "usage": body.get("usage")},
        )


def build_audio_provider() -> BaseAudioProvider:
    if settings.llm_api_key and settings.llm_base_url:
        return FallbackAudioProvider(
            primary=MiMoTokenPlanAudioProvider(),
            fallback=MockAudioProvider(),
        )
    return MockAudioProvider()


def _mock_silent_wav(*, duration_ms: int = 500, sample_rate: int = 8000) -> bytes:
    num_samples = max(1, sample_rate * duration_ms // 1000)
    data_size = num_samples * 2
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        sample_rate,
        sample_rate * 2,
        2,
        16,
        b"data",
        data_size,
    )
    return header + (b"\x00" * data_size)


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


def _asr_format(filename: str) -> str:
    lowered = filename.lower()
    if lowered.endswith(".mp3"):
        return "mp3"
    if lowered.endswith(".m4a"):
        return "m4a"
    if lowered.endswith(".webm"):
        return "webm"
    return "wav"


def _default_voice(text: str, model: str) -> str:
    if model == MIMO_TTS_VOICECLONE_MODEL:
        return "mimo_default"
    if any("\u4e00" <= char <= "\u9fff" for char in text):
        return "冰糖"
    return "Chloe"


def _build_tts_messages(
    text: str,
    model: str,
    *,
    speed: float,
    voice: str,
) -> list[dict[str, str]]:
    speed_hint = "稍快" if speed > 1.05 else "稍慢" if speed < 0.95 else "自然"
    if model == MIMO_TTS_VOICEDESIGN_MODEL:
        return [
            {
                "role": "user",
                "content": (
                    "A warm, clear Chinese teaching voice for undergraduate computer science courses. "
                    f"Speak at a {speed_hint} pace with friendly educational tone."
                ),
            },
            {"role": "assistant", "content": text},
        ]
    if model == MIMO_TTS_VOICECLONE_MODEL and voice.startswith("data:audio/"):
        return [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": text},
        ]
    style = (
        f"用清晰、温和的中文教学语气朗读，语速{speed_hint}，适合高校数据结构课程讲解。"
        if any("\u4e00" <= char <= "\u9fff" for char in text)
        else f"Use a clear educational tone at a {speed_hint} pace."
    )
    return [
        {"role": "user", "content": style},
        {"role": "assistant", "content": text},
    ]
