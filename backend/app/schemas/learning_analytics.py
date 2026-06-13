from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SessionHeartbeatRequest(BaseModel):
    session_id: UUID | None = None
    course_id: UUID | None = None
    page: str = Field(min_length=1, max_length=64)
    active: bool = True


class LearningAnalyticsSummary(BaseModel):
    period: Literal["week", "month"]
    active_seconds: int
    active_hours: float
    mastery: float | None = None
    daily: list[dict[str, object]] = []
    counts: dict[str, int] = {}
