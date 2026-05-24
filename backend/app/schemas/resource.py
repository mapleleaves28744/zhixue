from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


RESOURCE_TYPE_ALIASES: dict[str, str] = {
    "讲解": "explanation",
    "总结": "summary",
    "例题": "example",
    "复习卡": "flashcard",
    "错题解析": "review",
    "explain": "explanation",
    "note": "summary",
}

VALID_RESOURCE_TYPES = {"explanation", "summary", "example", "flashcard", "review"}


class ResourceGenerateRequest(BaseModel):
    course_id: UUID
    knowledge_id: UUID | None = None
    wiki_page_id: UUID | None = None
    resource_type: str = Field(min_length=1, max_length=64)
    requirement: str | None = Field(default=None, max_length=1000)
    use_profile: bool = True
    save_to_wiki: bool = False


class ResourceSaveToWikiRequest(BaseModel):
    wiki_page_id: UUID | None = None
    section_title: str | None = Field(default=None, max_length=120)


class GeneratedResourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    course_id: UUID
    knowledge_id: UUID | None = None
    wiki_page_id: UUID | None = None
    resource_type: str
    title: str
    content: str
    citations: list[Any] = Field(default_factory=list)
    personalized_reason: str | None = None
    model_name: str | None = None
    prompt_version_id: UUID | None = None
    status: str
    created_at: datetime


class ResourceGenerateResponse(BaseModel):
    resource_id: UUID
    title: str
    content: str
    citations: list[Any] = Field(default_factory=list)
    personalized_reason: str | None = None
    agent_run_id: UUID | None = None
    review_result: dict[str, Any] = Field(default_factory=dict)
    status: str
    wiki_page_id: UUID | None = None
