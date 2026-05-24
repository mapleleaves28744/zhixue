from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.knowledge import KnowledgePoint
    from app.models.prompt import PromptVersion
    from app.models.user import User
    from app.models.wiki import WikiPage


class GeneratedResource(Base):
    """AI 生成的个性化学习资源。"""

    __tablename__ = "generated_resources"
    __table_args__ = (
        Index("idx_generated_resources_user_course", "user_id", "course_id"),
        Index("idx_generated_resources_knowledge_id", "knowledge_id"),
        Index("idx_generated_resources_type", "resource_type"),
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
    knowledge_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("knowledge_points.id", ondelete="SET NULL"),
    )
    wiki_page_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("wiki_pages.id", ondelete="SET NULL"),
    )
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    personalized_reason: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(String(128))
    prompt_version_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("prompt_versions.id", ondelete="SET NULL"),
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

    user: Mapped[User] = relationship("User")
    course: Mapped[Course] = relationship("Course")
    knowledge: Mapped[KnowledgePoint | None] = relationship("KnowledgePoint")
    wiki_page: Mapped[WikiPage | None] = relationship("WikiPage")
    prompt_version: Mapped[PromptVersion | None] = relationship("PromptVersion")
