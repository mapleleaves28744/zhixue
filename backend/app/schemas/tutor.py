from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TutorChatRequest(BaseModel):
    course_id: UUID
    question: str = Field(min_length=1, max_length=2000)
    session_id: UUID | None = None
    knowledge_id: UUID | None = None
    wiki_page_id: UUID | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    use_rag: bool = True
    use_wiki: bool = True
    use_profile: bool = True
    stream: bool = False


class TutorCitation(BaseModel):
    source_type: str
    title: str
    source_id: str | None = None
    chunk_id: str | None = None
    page_id: str | None = None
    page_no: int | None = None
    score: float | None = None
    quote: str | None = None


class RelatedKnowledgePoint(BaseModel):
    knowledge_id: str | None = None
    name: str


class TutorChatResponse(BaseModel):
    answer: str
    citations: list[TutorCitation] = Field(default_factory=list)
    related_knowledge_points: list[RelatedKnowledgePoint] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    save_to_wiki_candidate: str | None = None
    agent_run_id: UUID | None = None
    review_result: dict[str, Any] = Field(default_factory=dict)
    memory_update_suggestion: dict[str, Any] = Field(default_factory=dict)
    message_id: UUID | None = None
    model: str | None = None
    provider: str | None = None
    fallback_used: bool = False
    failed_provider: str | None = None
    fallback_reason: str | None = None


class TutorSaveToWikiRequest(BaseModel):
    wiki_page_id: UUID
    section_title: str | None = Field(default=None, max_length=120)


class TutorFeedbackRequest(BaseModel):
    feedback_type: str = Field(min_length=1, max_length=64)
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)
