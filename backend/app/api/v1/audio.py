from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.deps import get_current_user
from app.core.response import success_response
from app.llm.audio_provider import (
    MIMO_TTS_MODEL,
    MIMO_TTS_VOICECLONE_MODEL,
    MIMO_TTS_VOICEDESIGN_MODEL,
    _safe_audio_byte_count,
    build_audio_provider,
)
from app.models.user import User
from app.schemas.audio import AudioSynthesizeRequest, AudioTranscribeRequest

router = APIRouter()


@router.post("/transcribe")
async def transcribe_audio(
    payload: AudioTranscribeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    result = await build_audio_provider().transcribe(
        payload.audio_base64,
        filename=payload.filename,
        language=payload.language,
    )
    raw = result.raw or {}
    return success_response(
        {
            "text": result.text,
            "duration_ms": result.duration_ms,
            "language": result.language,
            "provider": result.provider,
            "model": result.model,
            "audio_bytes": _safe_audio_byte_count(payload.audio_base64),
            "fallback_used": bool(raw.get("fallback_used")),
            "failed_provider": raw.get("failed_provider"),
            "fallback_reason": raw.get("fallback_reason"),
        },
        request=request,
    )


@router.post("/synthesize")
async def synthesize_speech(
    payload: AudioSynthesizeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    model_map = {
        "tts": MIMO_TTS_MODEL,
        "voiceclone": MIMO_TTS_VOICECLONE_MODEL,
        "voicedesign": MIMO_TTS_VOICEDESIGN_MODEL,
    }
    result = await build_audio_provider().synthesize(
        payload.text,
        voice=payload.voice,
        speed=payload.speed,
        response_format=payload.response_format,
        model=model_map.get(payload.model_type, MIMO_TTS_MODEL),
    )
    raw = result.raw or {}
    return success_response(
        {
            "audio_base64": result.audio_base64,
            "format": result.format,
            "model": result.model,
            "provider": result.provider,
            "duration_ms": result.duration_ms,
            "text_length": len(payload.text),
            "fallback_used": bool(raw.get("fallback_used")),
            "failed_provider": raw.get("failed_provider"),
            "fallback_reason": raw.get("fallback_reason"),
        },
        request=request,
    )
