from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AnalyzeRequest(BaseModel):
    course_id: UUID
    focus: str


class StrategyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    course_id: UUID | None = None
    strategy_type: str
    before_value: dict[str, Any] = {}
    after_value: dict[str, Any] = {}
    description: str | None = None
    status: str
    risk_level: str
    evidence: list[Any] = []
    previous_strategy_id: UUID | None = None
    version_no: int = 1
    created_at: datetime
    updated_at: datetime


class StrategyApplyRequest(BaseModel):
    strategy_id: UUID


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    course_id: UUID | None = None
    trigger_type: str
    focus: str
    input_snapshot: dict[str, Any] = {}
    strategies_generated: int = 0
    status: str
    error_message: str | None = None
    created_at: datetime
