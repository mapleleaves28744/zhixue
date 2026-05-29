from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WikiPageCreate(BaseModel):
    course_id: UUID
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    summary: str | None = None


class WikiPageUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = None
    summary: str | None = None
    change_message: str | None = Field(default=None, max_length=500)


class WikiPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_id: UUID
    owner_id: UUID
    title: str
    slug: str
    summary: str | None = None
    content: str
    status: str
    current_version: int
    extra_meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class WikiPageListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_id: UUID
    owner_id: UUID
    title: str
    slug: str
    summary: str | None = None
    status: str
    current_version: int
    created_at: datetime
    updated_at: datetime


class WikiPageVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    page_id: UUID
    version_number: int
    title: str
    content: str
    summary: str | None = None
    change_message: str | None = None
    created_by: UUID
    created_at: datetime


class WikiPageListQuery(BaseModel):
    course_id: UUID
    status: str | None = "active"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class WikiSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    page_id: UUID
    source_type: str
    source_id: UUID
    source_title: str | None = None
    quote_text: str | None = None
    extra_meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class WikiLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_page_id: UUID
    target_page_id: UUID
    relation_type: str
    created_at: datetime


class GenerateFromMaterialRequest(BaseModel):
    course_id: UUID
    material_id: UUID


class UpdateFromNoteRequest(BaseModel):
    page_id: UUID
    note_content: str = Field(min_length=1)
