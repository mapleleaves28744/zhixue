from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID


GroundingStatus = Literal["grounded", "partial", "insufficient"]


@dataclass(frozen=True)
class EvidenceItem:
    citation_key: str
    source_type: Literal["document", "wiki"]
    source_id: UUID
    title: str
    quote: str
    chunk_id: UUID | None = None
    page_id: UUID | None = None
    knowledge_id: UUID | None = None
    page_no: int | None = None
    retrieval_mode: str = "hybrid"
    vector_score: float = 0.0
    keyword_score: float = 0.0
    rerank_score: float = 0.0
    confidence: Literal["strong", "acceptable"] = "acceptable"

    def as_citation(self) -> dict[str, object]:
        return {
            "citation_key": self.citation_key,
            "source_type": self.source_type,
            "title": self.title,
            "source_id": str(self.source_id),
            "chunk_id": str(self.chunk_id) if self.chunk_id else None,
            "page_id": str(self.page_id) if self.page_id else None,
            "knowledge_id": str(self.knowledge_id) if self.knowledge_id else None,
            "page_no": self.page_no,
            "score": round(self.rerank_score, 6),
            "quote": self.quote,
            "retrieval_mode": self.retrieval_mode,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class GraphContext:
    seed_knowledge_ids: list[UUID] = field(default_factory=list)
    expanded_knowledge_ids: list[UUID] = field(default_factory=list)
    relation_paths: list[dict[str, object]] = field(default_factory=list)


@dataclass(frozen=True)
class EvidenceBundle:
    evidence: list[EvidenceItem]
    graph_context: GraphContext
    candidate_count: int


@dataclass(frozen=True)
class CitationValidationResult:
    citations: list[EvidenceItem]
    unknown_keys: list[str]
    grounding_status: GroundingStatus
    grounding_message: str
