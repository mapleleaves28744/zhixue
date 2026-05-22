from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.material import CourseMaterial
    from app.models.profile import LearningPreference
    from app.models.user import User


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        Index("idx_courses_owner_id", "owner_id"),
        Index("idx_courses_visibility", "visibility"),
        Index("idx_courses_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    owner_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    course_code: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(String(128))
    cover_url: Mapped[str | None] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'private'"),
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'active'"),
    )
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

    owner: Mapped[User] = relationship("User", back_populates="courses")
    materials: Mapped[list[CourseMaterial]] = relationship(
        "CourseMaterial",
        back_populates="course",
    )
    learning_preferences: Mapped[list[LearningPreference]] = relationship(
        "LearningPreference",
        back_populates="course",
    )
