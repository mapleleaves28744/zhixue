from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


CourseVisibility = Literal["private", "public_template"]
CourseStatusFilter = Literal["active", "archived", "all"]


class CourseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    course_code: str | None = Field(default=None, max_length=64)
    description: str | None = None
    subject: str | None = Field(default=None, max_length=128)
    cover_url: str | None = None
    visibility: CourseVisibility = "private"


class CourseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=128)
    course_code: str | None = Field(default=None, max_length=64)
    description: str | None = None
    subject: str | None = Field(default=None, max_length=128)
    cover_url: str | None = None
    visibility: CourseVisibility | None = None


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    title: str
    course_code: str | None = None
    description: str | None = None
    subject: str | None = None
    cover_url: str | None = None
    visibility: str
    status: str
    created_at: datetime
    updated_at: datetime
