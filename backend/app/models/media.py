from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MediaAsset(Base):
    """多模态产物：图片、视频、音频、互动课件、代码包等。"""

    __tablename__ = "media_assets"
    __table_args__ = (
        Index("idx_media_assets_user_course", "user_id", "course_id"),
        Index("idx_media_assets_resource", "resource_id"),
        Index("idx_media_assets_agent_task", "agent_task_id"),
        Index("idx_media_assets_type_status", "asset_type", "status"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("generated_resources.id", ondelete="SET NULL"))
    agent_task_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("agent_tasks.id", ondelete="SET NULL"))
    conversation_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("agent_conversations.id", ondelete="SET NULL"))
    tool_call_id: Mapped[str | None] = mapped_column(String(128))

    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    thumbnail_path: Mapped[str | None] = mapped_column(Text)

    provider: Mapped[str | None] = mapped_column(String(64))
    model_name: Mapped[str | None] = mapped_column(String(128))
    prompt: Mapped[str | None] = mapped_column(Text)
    negative_prompt: Mapped[str | None] = mapped_column(Text)

    citations: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    safety_result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    render_meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    resource = relationship("GeneratedResource")


class MediaJob(Base):
    """多模态异步任务：视频渲染、远程 T2V 轮询、课件生成等。"""

    __tablename__ = "media_jobs"
    __table_args__ = (
        Index("idx_media_jobs_user_course", "user_id", "course_id"),
        Index("idx_media_jobs_status", "status"),
        Index("idx_media_jobs_agent_task", "agent_task_id"),
        Index("idx_media_jobs_idempotency", "idempotency_key", unique=True),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("generated_resources.id", ondelete="SET NULL"))
    asset_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="SET NULL"))
    agent_task_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("agent_tasks.id", ondelete="SET NULL"))
    conversation_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("agent_conversations.id", ondelete="SET NULL"))
    tool_call_id: Mapped[str | None] = mapped_column(String(128))

    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_job_id: Mapped[str | None] = mapped_column(String(255))

    input_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    output_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    progress: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    stage: Mapped[str] = mapped_column(String(64), nullable=False, server_default="queued")
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="queued")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    asset = relationship("MediaAsset")
    resource = relationship("GeneratedResource")
