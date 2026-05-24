from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class ChatResponse:
    content: str
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    provider: str = ""

    @property
    def prompt_tokens(self) -> int:
        return self.usage.get("prompt_tokens", 0)

    @property
    def completion_tokens(self) -> int:
        return self.usage.get("completion_tokens", 0)

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)


@dataclass
class EmbeddingResponse:
    embeddings: list[list[float]]
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    provider: str = ""

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)


@dataclass
class LLMModelConfig:
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2048
    embedding_model: str | None = None
    timeout_seconds: int | None = None


@dataclass
class LLMCallContext:
    user_id: UUID | None = None
    course_id: UUID | None = None
    agent_run_id: UUID | None = None
    prompt_version_id: UUID | None = None
