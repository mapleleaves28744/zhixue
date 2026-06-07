from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


ALLOWED_LEARNING_EVENT_TYPES = {
    "page_view",
    "resource_read",
    "quiz_start",
    "quiz_complete",
    "wiki_read",
    "tutor_ask",
    "practice_mistake",
    "profile_updated",
    "diagnosis_generated",
    "recommendation_view",
    "recommendation_click",
}


class LearningEventCreate(BaseModel):
    course_id: UUID | None = None
    knowledge_id: UUID | None = None
    event_type: str = Field(min_length=1, max_length=64)
    event_source: str | None = Field(default="frontend", max_length=64)
    event_payload: dict[str, Any] = Field(default_factory=dict)


class LearningEventBatchRequest(BaseModel):
    events: list[LearningEventCreate] = Field(min_length=1, max_length=50)
