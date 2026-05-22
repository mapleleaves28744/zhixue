from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


MaterialParseStatus = Literal["pending", "processing", "success", "failed"]


class MaterialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_id: UUID
    uploaded_by: UUID
    file_name: str
    file_type: str
    file_size: int
    storage_path: str
    parse_status: str
    parse_error: str | None = None
    text_hash: str | None = None
    extra_meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class MaterialUploadResponse(MaterialRead):
    pass


class MaterialParseResult(BaseModel):
    id: UUID
    course_id: UUID
    file_name: str
    file_type: str
    parse_status: str
    parse_error: str | None = None
    text_hash: str | None = None
    text_length: int = 0
    parsed_text_path: str | None = None
