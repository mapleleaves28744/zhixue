from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    major: str | None = None
    grade: str | None = None
    learning_goal: str | None = None
    profile_summary: str | None = None
    mastery_snapshot: dict[str, Any] = {}
    weak_points: list[Any] = []
    error_patterns: list[Any] = []
    strategy_summary: dict[str, Any] = {}
    version_no: int = 1
    created_at: datetime
    updated_at: datetime


class ProfileUpdate(BaseModel):
    major: str | None = None
    grade: str | None = None
    learning_goal: str | None = None


class ProfileSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    profile_summary: str | None = None
    mastery_snapshot: dict[str, Any] = {}
    weak_points: list[Any] = []
    error_patterns: list[Any] = []
    strategy_summary: dict[str, Any] = {}


class LearningPreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    course_id: UUID | None = None
    answer_length: str | None = None
    explanation_style: str | None = None
    resource_preferences: list[Any] = []
    confidence: float = 0.8
    version_no: int = 1
