from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LearningPathGenerateRequest(BaseModel):
    course_id: UUID
    goal: str = Field(default="补强当前薄弱知识点", min_length=1, max_length=500)
    target_knowledge_ids: list[UUID] = Field(default_factory=list)
    path_type: str = Field(default="weakness_repair", max_length=64)


class LearningPathItemUpdate(BaseModel):
    status: str = Field(pattern="^(pending|doing|completed|skipped)$")


class LearningPathItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    path_id: UUID
    knowledge_id: UUID | None = None
    wiki_page_id: UUID | None = None
    title: str
    item_type: str
    order_index: int
    status: str
    reason: str | None = None
    estimated_minutes: int | None = None
    completed_at: datetime | None = None
    created_at: datetime


class LearningPathRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    course_id: UUID
    title: str
    goal: str | None = None
    reason: str | None = None
    status: str
    progress: float = 0
    strategy_version_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    items: list[LearningPathItemRead] = Field(default_factory=list)
