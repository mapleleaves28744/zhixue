from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent_task import AgentTaskRead


class AgentConversationCreateRequest(BaseModel):
    course_id: UUID
    title: str | None = Field(default=None, max_length=255)


class AgentConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    course_id: UUID | None = None
    thread_id: str
    title: str
    status: str
    summary: str | None = None
    extra_meta: dict[str, Any] = Field(default_factory=dict)
    last_message_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AgentMessageCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    tool_hints: list[str] = Field(default_factory=list, max_length=10)
    skip_tools: list[str] = Field(default_factory=list, max_length=10)


class AgentMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    user_id: UUID
    task_id: UUID | None = None
    role: str
    message_type: str
    content: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AgentTaskEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    conversation_id: UUID | None = None
    sequence_no: int
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AgentMessageAccepted(BaseModel):
    conversation: AgentConversationRead
    message: AgentMessageRead
    task: AgentTaskRead
    queued: bool = True


class AgentTaskResumeRequest(BaseModel):
    approved: bool = True
