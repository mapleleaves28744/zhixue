from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.evolution import EvolutionStrategy
    from app.models.knowledge import KnowledgePoint
    from app.models.user import User
    from app.models.wiki import WikiPage


class LearningPath(Base):
    __tablename__ = "learning_paths"
    __table_args__ = (
        Index("idx_learning_paths_user_course", "user_id", "course_id"),
        Index("idx_learning_paths_status", "status"),
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
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    goal: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'active'"),
    )
    progress: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default=text("0"),
    )
    strategy_version_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("evolution_strategies.id", ondelete="SET NULL"),
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

    user: Mapped[User] = relationship("User")
    course: Mapped[Course] = relationship("Course", back_populates="learning_paths")
    strategy_version: Mapped[EvolutionStrategy | None] = relationship("EvolutionStrategy")
    items: Mapped[list[LearningPathItem]] = relationship(
        "LearningPathItem",
        back_populates="path",
        order_by="LearningPathItem.order_index",
        cascade="all, delete-orphan",
    )


class LearningPathItem(Base):
    __tablename__ = "learning_path_items"
    __table_args__ = (
        Index("idx_learning_path_items_path_id", "path_id"),
        Index("idx_learning_path_items_knowledge_id", "knowledge_id"),
        Index("idx_learning_path_items_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    path_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("learning_paths.id", ondelete="CASCADE"),
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
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    item_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default=text("'learn'"),
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'pending'"),
    )
    reason: Mapped[str | None] = mapped_column(Text)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    path: Mapped[LearningPath] = relationship("LearningPath", back_populates="items")
    knowledge: Mapped[KnowledgePoint | None] = relationship("KnowledgePoint")
    wiki_page: Mapped[WikiPage | None] = relationship("WikiPage")
