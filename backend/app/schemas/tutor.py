from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TutorPerformance(BaseModel):
    retrieval_ms: int = 0
    first_token_ms: int | None = None
    generation_ms: int = 0
    total_ms: int = 0
    llm_call_count: int = 0
    evidence_candidate_count: int = 0
    evidence_accepted_count: int = 0


class TutorChatRequest(BaseModel):
    course_id: UUID
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None
    session_id: UUID | None = None
    knowledge_id: UUID | None = None
    wiki_page_id: UUID | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    use_rag: bool = True
    use_wiki: bool = True
    use_profile: bool = True
    stream: bool = False


class TutorCitation(BaseModel):
    citation_key: str | None = None
    source_type: str
    title: str
    source_id: str | None = None
    chunk_id: str | None = None
    page_id: str | None = None
    knowledge_id: str | None = None
    page_no: int | None = None
    score: float | None = None
    quote: str | None = None
    retrieval_mode: str | None = None
    confidence: str | None = None


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
    conversation_id: UUID | None = None
    model: str | None = None
    provider: str | None = None
    fallback_used: bool = False
    failed_provider: str | None = None
    fallback_reason: str | None = None
    knowledge_extract: dict[str, Any] = Field(default_factory=dict)
    graph_context: dict[str, Any] = Field(default_factory=dict)
    grounding_status: Literal["grounded", "partial", "insufficient"] = "insufficient"
    grounding_message: str = "课程资料未找到可靠依据。"
    performance: TutorPerformance = Field(default_factory=TutorPerformance)
    postprocess_status: Literal["queued", "skipped"] = "skipped"


class TutorSaveToWikiRequest(BaseModel):
    wiki_page_id: UUID
    section_title: str | None = Field(default=None, max_length=120)


class TutorFeedbackRequest(BaseModel):
    feedback_type: str = Field(min_length=1, max_length=64)
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)
