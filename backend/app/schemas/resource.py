from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


RESOURCE_TYPE_ALIASES: dict[str, str] = {
    "讲解": "explanation",
    "总结": "summary",
    "例题": "example",
    "复习卡": "flashcard",
    "错题解析": "review",
    "思维导图": "image",
    "脑图": "image",
    "图解": "image",
    "流程图": "image",
    "架构图": "image",
    "explain": "explanation",
    "note": "summary",
    "mind_map": "image",
    "mindmap": "image",
    "diagram": "image",
    "图片": "image",
    "教学插图": "image",
    "视频": "video",
    "讲解视频": "video",
    "动画": "animation",
    "互动课件": "interactive_courseware",
    "交互课件": "interactive_courseware",
    "沉浸课堂": "immersive_classroom",
    "沉浸式课堂": "immersive_classroom",
    "代码实操": "code_project",
    "实践项目": "code_project",
    "拓展阅读": "reading_pack",
}

VALID_RESOURCE_TYPES = {
    "explanation",
    "summary",
    "example",
    "flashcard",
    "review",
    "mindmap",
    "diagram",
    "image",
    "video",
    "animation",
    "interactive_courseware",
    "immersive_classroom",
    "code_project",
    "reading_pack",
}


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
    media_asset_id: UUID | None = None
    media_mime_type: str | None = None
    media_asset_type: str | None = None
    media_file_url: str | None = None
    content_format: str | None = None
    preview_mode: str | None = None
    media_job_id: UUID | None = None
    job_status: str | None = None
    preview_video_asset_id: UUID | None = None
    preview_video_mime_type: str | None = None


class ExternalResourceItemRead(BaseModel):
    kind: Literal["video", "blog", "repo"]
    topic: str = ""
    title: str
    url: str
    snippet: str = ""
    source_domain: str = ""
    reason: str = ""


class ExternalResourceFeedRead(BaseModel):
    primary_topic: str
    topics: list[str] = Field(default_factory=list)
    reason: str
    items: list[ExternalResourceItemRead] = Field(default_factory=list)
    cached: bool = False
    prepush_status: str = "none"
    provider: str = "anysearch"
    message: str = ""


class ResourceGenerateResponse(BaseModel):
    resource_id: UUID
    id: UUID
    resource_type: str
    title: str
    content: str
    citations: list[Any] = Field(default_factory=list)
    personalized_reason: str | None = None
    agent_run_id: UUID | None = None
    review_result: dict[str, Any] = Field(default_factory=dict)
    status: str
    wiki_page_id: UUID | None = None
    created_at: datetime
    media_asset_id: UUID | None = None
    media_mime_type: str | None = None
    media_asset_type: str | None = None
    media_file_url: str | None = None
    content_format: str | None = None
    preview_mode: str | None = None
    media_job_id: UUID | None = None
    job_status: str | None = None
    job_message: str | None = None
