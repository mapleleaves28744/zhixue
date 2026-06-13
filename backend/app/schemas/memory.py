from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


def _normalize_evidence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    return [value]


class MemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    course_id: UUID | None = None
    memory_type: str
    memory_key: str
    content: str
    evidence: list[Any] = []
    confidence: float = 0.8
    status: str = "active"
    salience: float = 0.5
    reinforcement_count: int = 1
    last_reinforced_at: datetime | None = None
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("evidence", mode="before")
    @classmethod
    def coerce_evidence(cls, value: Any) -> list[Any]:
        return _normalize_evidence(value)


class MemoryUpdate(BaseModel):
    content: str | None = None
    memory_type: str | None = None


class MemoryHealth(BaseModel):
    active_count: int
    archived_count: int
    capacity: int
    remaining: int
