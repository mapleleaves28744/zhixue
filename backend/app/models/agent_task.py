from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.agent import AgentRun
    from app.models.course import Course
    from app.models.user import User


class AgentTask(Base):
    __tablename__ = "agent_tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','planned','queued','waiting_confirmation','running','succeeded','failed','cancelled')",
            name="ck_agent_tasks_status",
        ),
        Index("idx_agent_tasks_user_course", "user_id", "course_id"),
        Index("idx_agent_tasks_user_status", "user_id", "status"),
        Index("idx_agent_tasks_created_at", "created_at"),
        Index("idx_agent_tasks_conversation", "conversation_id"),
        Index("idx_agent_tasks_thread_id", "thread_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("agent_conversations.id", ondelete="SET NULL")
    )
    thread_id: Mapped[str | None] = mapped_column(String(128))
    task_goal: Mapped[str] = mapped_column(Text, nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    plan_schema_version: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'1.0'")
    )
    graph_version: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'langgraph-1.0'")
    )
    runtime_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'langgraph'")
    )
    plan_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    input_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    intent_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    risk_level: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'low'")
    )
    requires_confirmation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    iteration_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    tool_call_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    replan_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    checkpoint_id: Mapped[str | None] = mapped_column(String(255))
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship("User")
    course: Mapped[Course] = relationship("Course")
    steps: Mapped[list[AgentTaskStep]] = relationship(
        "AgentTaskStep",
        back_populates="task",
        order_by="AgentTaskStep.step_index",
        cascade="all, delete-orphan",
    )


class AgentTaskStep(Base):
    __tablename__ = "agent_task_steps"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','running','succeeded','failed','skipped')",
            name="ck_agent_task_steps_status",
        ),
        UniqueConstraint("task_id", "step_index", name="uq_agent_task_steps_task_index"),
        Index("idx_agent_task_steps_task_id", "task_id"),
        Index("idx_agent_task_steps_task_status", "task_id", "status"),
        Index("idx_agent_task_steps_tool_call_id", "tool_call_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    task_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    skill_name: Mapped[str | None] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    expected_output: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'pending'")
    )
    input_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    output_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    evidence: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    artifact_refs: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    related_agent_run_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL")
    )
    tool_call_id: Mapped[str | None] = mapped_column(String(128))
    parent_step_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("agent_task_steps.id", ondelete="SET NULL")
    )
    iteration_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    node_name: Mapped[str | None] = mapped_column(String(128))
    decision_summary: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    task: Mapped[AgentTask] = relationship("AgentTask", back_populates="steps")
    related_agent_run: Mapped[AgentRun | None] = relationship("AgentRun")
