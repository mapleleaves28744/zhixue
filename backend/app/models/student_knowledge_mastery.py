from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.knowledge import KnowledgePoint
    from app.models.user import User


class StudentKnowledgeMastery(Base):
    __tablename__ = "student_knowledge_mastery"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", "knowledge_id", name="uq_student_knowledge_mastery"),
        Index("idx_skm_user_course", "user_id", "course_id"),
        Index("idx_skm_knowledge_id", "knowledge_id"),
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
    course_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    knowledge_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        nullable=False,
    )
    mastery_score: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0.0"))
    stability: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("1.0"))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    ask_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_practiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_asked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped[User] = relationship("User")
    course: Mapped[Course] = relationship("Course")
    knowledge_point: Mapped[KnowledgePoint] = relationship("KnowledgePoint")
