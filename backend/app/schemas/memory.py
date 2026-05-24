from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    course_id: UUID | None = None
    memory_type: str
    content: str
    evidence: list[Any] = []
    confidence: float = 0.8
    created_at: datetime
    updated_at: datetime


class MemoryUpdate(BaseModel):
    content: str | None = None
    memory_type: str | None = None
