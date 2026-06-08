from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EducationalImageGenerateRequest(BaseModel):
    course_id: UUID
    topic: str = Field(min_length=1, max_length=200)
    image_type: Literal["concept_illustration", "process_visual", "analogy", "cover", "summary_card"] = "concept_illustration"
    style: str | None = Field(default="clean educational illustration", max_length=200)
    size: str = Field(default="1280x720", pattern=r"^\d{3,4}x\d{3,4}$")
    requirement: str | None = Field(default=None, max_length=1000)
    use_profile: bool = True


class LessonVideoGenerateRequest(BaseModel):
    course_id: UUID
    topic: str = Field(min_length=1, max_length=200)
    duration_seconds: int = Field(default=90, ge=30, le=240)
    visual_mode: Literal["animated_diagram", "t2v_broll", "mixed", "storyboard"] = "storyboard"
    voice: str | None = Field(default=None, max_length=100)
    target_level: str | None = Field(default=None, max_length=100)
    include_subtitles: bool = True
    use_profile: bool = True


class StoryboardHtmlGenerateRequest(BaseModel):
    course_id: UUID
    topic: str = Field(min_length=1, max_length=200)
    duration_seconds: int = Field(default=90, ge=30, le=240)
    requirement: str | None = Field(default=None, max_length=1000)
    use_profile: bool = True


class InteractiveCoursewareGenerateRequest(BaseModel):
    course_id: UUID
    topic: str = Field(min_length=1, max_length=200)
    interaction_type: Literal["stepper", "drag_sort", "quiz_simulation", "graph_traversal", "timeline"] = "stepper"
    target_level: str | None = Field(default=None, max_length=100)
    requirement: str | None = Field(default=None, max_length=1000)
    use_profile: bool = True


class MediaAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    course_id: UUID
    resource_id: UUID | None = None
    agent_task_id: UUID | None = None
    conversation_id: UUID | None = None
    tool_call_id: str | None = None
    asset_type: str
    title: str
    description: str | None = None
    mime_type: str
    file_size: int | None = None
    duration_ms: int | None = None
    provider: str | None = None
    model_name: str | None = None
    citations: list[Any] = Field(default_factory=list)
    safety_result: dict[str, Any] = Field(default_factory=dict)
    render_meta: dict[str, Any] = Field(default_factory=dict)
    status: str
    created_at: datetime
    updated_at: datetime

    @property
    def file_url(self) -> str:
        return f"/api/v1/media-assets/{self.id}/file"


class MediaJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    course_id: UUID
    resource_id: UUID | None = None
    asset_id: UUID | None = None
    agent_task_id: UUID | None = None
    job_type: str
    provider: str
    stage: str
    status: str
    progress: int
    output_payload: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None
