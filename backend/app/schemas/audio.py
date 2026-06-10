from __future__ import annotations

from pydantic import BaseModel, Field


class AudioTranscribeRequest(BaseModel):
    audio_base64: str = Field(min_length=1)
    filename: str = Field(default="audio.wav", max_length=255)
    language: str = Field(default="zh", max_length=16)


class AudioSynthesizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    model_type: str = Field(default="tts", pattern="^(tts|voiceclone|voicedesign)$")
    voice: str | None = Field(default=None, max_length=128)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    response_format: str = Field(default="wav", pattern="^(wav|mp3)$")
