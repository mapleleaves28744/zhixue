from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeSearchRequest(BaseModel):
    course_id: UUID
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=50)
    knowledge_id: UUID | None = None


class KnowledgeSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: UUID
    content: str
    score: float
    source_title: str | None = None
    page_no: int | None = None
    material_id: UUID


class ExtractKnowledgeRequest(BaseModel):
    material_id: UUID


class KnowledgePointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_id: UUID
    name: str
    chapter: str | None = None
    description: str | None = None
    difficulty: str | None = None
    importance: str | None = None
    sort_order: int = 0
    extra_meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
