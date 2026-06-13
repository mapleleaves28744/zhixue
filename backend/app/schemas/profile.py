from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
    prompt_params: dict[str, Any] = {}
    confidence: float = 0.8
    version_no: int = 1
    created_at: datetime
    updated_at: datetime


class ProfileDialogueIngestRequest(BaseModel):
    course_id: UUID | None = None
    dialogue_text: str = Field(min_length=1, max_length=5000)
    source_message_id: str | None = Field(default=None, max_length=128)


class ProfileDialogueIngestResult(BaseModel):
    profile: ProfileRead
    preferences: LearningPreferenceRead | None = None
    signals: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)


class CourseProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    course_id: UUID
    learning_goal: str | None = None
    profile_summary: str | None = None
    mastery_snapshot: dict[str, Any] = {}
    weak_points: list[Any] = []
    error_patterns: list[Any] = []
    strategy_summary: dict[str, Any] = {}
    evidence: list[Any] = []
    version_no: int = 1
    created_at: datetime
    updated_at: datetime
