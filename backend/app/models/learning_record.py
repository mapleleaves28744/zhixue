from __future__ import annotations

from datetime import datetime
from typing import Any, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.user import User


class LearningRecord(Base):
    __tablename__ = "learning_records"
    __table_args__ = (
        Index("idx_learning_records_user_id", "user_id"),
        Index("idx_learning_records_course_id", "course_id"),
        Index("idx_learning_records_event_type", "event_type"),
        Index("idx_learning_records_created_at", "created_at"),
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
    knowledge_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_source: Mapped[str | None] = mapped_column(String(64))
    event_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped[User] = relationship("User", back_populates="learning_records")
    course: Mapped[Course | None] = relationship("Course")
