from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.knowledge import KnowledgePoint


class KnowledgeRelation(Base):
    __tablename__ = "knowledge_relations"
    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "source_knowledge_id",
            "target_knowledge_id",
            "relation_type",
            "scope",
            name="uq_knowledge_relations_edge",
        ),
        Index("idx_knowledge_relations_course_id", "course_id"),
        Index("idx_knowledge_relations_source", "source_knowledge_id"),
        Index("idx_knowledge_relations_target", "target_knowledge_id"),
        Index("idx_knowledge_relations_scope", "scope"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    course_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_knowledge_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_knowledge_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        nullable=False,
    )
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'public'"))
    evidence: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("1.0"))
    created_by: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'seed'"))
    extra_meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    course: Mapped[Course] = relationship("Course")
    source_knowledge: Mapped[KnowledgePoint] = relationship(
        "KnowledgePoint",
        foreign_keys=[source_knowledge_id],
    )
    target_knowledge: Mapped[KnowledgePoint] = relationship(
        "KnowledgePoint",
        foreign_keys=[target_knowledge_id],
    )
