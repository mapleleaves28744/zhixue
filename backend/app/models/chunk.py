from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

try:
    from pgvector.sqlalchemy import Vector
    HAS_VECTOR = True
except ImportError:
    HAS_VECTOR = False

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.knowledge import KnowledgePoint
    from app.models.material import CourseMaterial


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("idx_document_chunks_material_id", "material_id"),
        Index("idx_document_chunks_course_id", "course_id"),
        Index("idx_document_chunks_knowledge_id", "knowledge_id"),
        Index("idx_document_chunks_chunk_index", "chunk_index"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    material_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("course_materials.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    knowledge_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("knowledge_points.id", ondelete="SET NULL"),
        nullable=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    page_no: Mapped[int | None] = mapped_column(Integer)
    source_title: Mapped[str | None] = mapped_column(String(255))
    embedding = mapped_column(Vector(1024) if HAS_VECTOR else Text, nullable=True)
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

    material: Mapped[CourseMaterial] = relationship("CourseMaterial")
    course: Mapped[Course] = relationship("Course")
    knowledge: Mapped[KnowledgePoint | None] = relationship("KnowledgePoint")
