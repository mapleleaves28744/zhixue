from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class StudentMemory(Base):
    __tablename__ = "student_memories"
    __table_args__ = (
        Index("idx_student_memories_user_id", "user_id"),
        Index("idx_student_memories_course_id", "course_id"),
        Index("idx_student_memories_active_rank", "user_id", "course_id", "status", "salience"),
        Index("idx_student_memories_scope_key", "user_id", "course_id", "memory_key"),
        Index("uq_student_memories_global_fact_active", "user_id", "fact_key", unique=True,
              postgresql_where=text("course_id IS NULL AND status = 'active' AND fact_key IS NOT NULL")),
        Index("uq_student_memories_course_fact_active", "user_id", "course_id", "fact_key", unique=True,
              postgresql_where=text("course_id IS NOT NULL AND status = 'active' AND fact_key IS NOT NULL")),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="SET NULL"),
    )
    memory_type: Mapped[str] = mapped_column(String(64), nullable=False)
    memory_key: Mapped[str] = mapped_column(String(255), nullable=False)
    fact_key: Mapped[str | None] = mapped_column(String(255))
    origin: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'legacy'"))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    lifecycle_meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        server_default=text("0.8000"),
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'active'"))
    salience: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, server_default=text("0.5000"))
    reinforcement_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    last_reinforced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped[User] = relationship("User", back_populates="memories")


class MemoryReflectionState(Base):
    __tablename__ = "memory_reflection_states"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", name="uq_memory_reflection_states_scope"),
        Index("uq_memory_reflection_states_global", "user_id", unique=True,
              postgresql_where=text("course_id IS NULL")),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"))
    last_record_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_record_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    memory_revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class StudentMemoryEvent(Base):
    __tablename__ = "student_memory_events"
    __table_args__ = (UniqueConstraint("memory_id", "operation_id", name="uq_student_memory_events_operation"),)

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    memory_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("student_memories.id", ondelete="CASCADE"), nullable=False)
    operation_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    actor: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    before_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    after_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    source_refs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class StudentMemoryEvidence(Base):
    __tablename__ = "student_memory_evidence"
    __table_args__ = (UniqueConstraint("memory_id", "source_type", "source_id", "stance", name="uq_student_memory_evidence_source"),)

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    memory_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("student_memories.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    stance: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'support'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MemoryReflectionJob(Base):
    __tablename__ = "memory_reflection_jobs"
    __table_args__ = (
        UniqueConstraint("source_record_id", "extractor_version", name="uq_memory_reflection_jobs_source_version"),
        Index("idx_memory_reflection_jobs_pending", "status", "retry_at"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"))
    source_record_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("learning_records.id", ondelete="CASCADE"), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'v1'"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'pending'"))
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    candidate_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
