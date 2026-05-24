from __future__ import annotations

from datetime import datetime
from typing import Any, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.user import User


class EvolutionStrategy(Base):
    """策略版本表 — 每条策略变更是一行记录，通过 previous_strategy_id 形成版本链"""

    __tablename__ = "evolution_strategies"
    __table_args__ = (
        Index("idx_evolution_strategies_user_course", "user_id", "course_id"),
        Index("idx_evolution_strategies_status", "status"),
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
    strategy_type: Mapped[str] = mapped_column(String(64), nullable=False)
    before_value: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    after_value: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'draft'"),
    )
    risk_level: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'low'"),
    )
    evidence: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    previous_strategy_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("evolution_strategies.id", ondelete="SET NULL"),
    )
    version_no: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1"),
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
    course: Mapped[Course | None] = relationship("Course")
    previous_strategy: Mapped[EvolutionStrategy | None] = relationship(
        "EvolutionStrategy", remote_side=[id], foreign_keys=[previous_strategy_id],
    )


class EvolutionEvent(Base):
    """自进化事件表 — 每次触发分析产生一条事件记录"""

    __tablename__ = "evolution_events"
    __table_args__ = (
        Index("idx_evolution_events_user_course", "user_id", "course_id"),
        Index("idx_evolution_events_status", "status"),
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
    trigger_type: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'manual'"),
    )
    focus: Mapped[str] = mapped_column(String(256), nullable=False)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    strategies_generated: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"),
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'pending'"),
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped[User] = relationship("User")
    course: Mapped[Course | None] = relationship("Course")
