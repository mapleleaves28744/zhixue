"""A/B 测试模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ABTest(Base):
    """A/B 测试实验定义。"""
    __tablename__ = "ab_tests"
    __table_args__ = (Index("idx_ab_tests_course_status", "course_id", "status"),)

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"),
    )
    course_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    test_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="strategy",
        comment="实验类型: strategy / prompt / difficulty",
    )
    control_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb"),
        comment="对照组配置",
    )
    treatment_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb"),
        comment="实验组配置",
    )
    traffic_split: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5,
        comment="实验组流量比例 0-1",
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft",
        comment="状态: draft / running / paused / completed",
    )
    winner: Mapped[str | None] = mapped_column(
        String(32), comment="胜出组: control / treatment / null",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    assignments: Mapped[list[ABTestAssignment]] = relationship(
        "ABTestAssignment", back_populates="test", cascade="all, delete-orphan",
    )


class ABTestAssignment(Base):
    """用户分组分配记录。"""
    __tablename__ = "ab_test_assignments"
    __table_args__ = (
        Index("idx_ab_assignments_test_user", "test_id", "user_id", unique=True),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"),
    )
    test_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("ab_tests.id", ondelete="CASCADE"), nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    group: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="分配组: control / treatment",
    )
    metric_value: Mapped[float | None] = mapped_column(Float, comment="实验指标值")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    test: Mapped[ABTest] = relationship("ABTest", back_populates="assignments")
