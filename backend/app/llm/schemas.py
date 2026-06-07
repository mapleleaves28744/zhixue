from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    type: str = "function"

    def as_openai_dict(self) -> dict[str, Any]:
        import json

        return {
            "id": self.id,
            "type": self.type,
            "function": {
                "name": self.name,
                "arguments": json.dumps(self.arguments, ensure_ascii=False),
            },
        }


@dataclass
class ChatMessage:
    role: str  # "system" | "developer" | "user" | "assistant" | "tool"
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    reasoning_content: str | None = None

    def as_openai_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.name:
            payload["name"] = self.name
        if self.tool_call_id:
            payload["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            payload["tool_calls"] = [item.as_openai_dict() for item in self.tool_calls]
        if self.reasoning_content and self.role == "assistant":
            payload["reasoning_content"] = self.reasoning_content
        return payload


@dataclass
class ChatResponse:
    content: str
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    provider: str = ""
    finish_reason: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    reasoning_content: str | None = None

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
