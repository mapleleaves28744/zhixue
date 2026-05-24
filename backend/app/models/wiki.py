from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.user import User


class WikiPage(Base):
    __tablename__ = "wiki_pages"
    __table_args__ = (
        UniqueConstraint("course_id", "owner_id", "slug", name="uq_wiki_pages_course_owner_slug"),
        Index("idx_wiki_pages_course_id", "course_id"),
        Index("idx_wiki_pages_owner_id", "owner_id"),
        Index("idx_wiki_pages_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    course_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'active'"))
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    extra_meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
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

    course: Mapped[Course] = relationship("Course")
    owner: Mapped[User] = relationship("User")
    versions: Mapped[list[WikiPageVersion]] = relationship(
        "WikiPageVersion", back_populates="page", order_by="WikiPageVersion.version_number"
    )
    sources: Mapped[list[WikiSource]] = relationship("WikiSource", back_populates="page")


class WikiPageVersion(Base):
    __tablename__ = "wiki_page_versions"
    __table_args__ = (
        UniqueConstraint("page_id", "version_number", name="uq_wiki_page_versions_page_ver"),
        Index("idx_wiki_page_versions_page_id", "page_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    page_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("wiki_pages.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    change_message: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    page: Mapped[WikiPage] = relationship("WikiPage", back_populates="versions")
    author: Mapped[User] = relationship("User")


class WikiLink(Base):
    __tablename__ = "wiki_links"
    __table_args__ = (
        UniqueConstraint(
            "source_page_id", "target_page_id", "relation_type",
            name="uq_wiki_links_source_target_type",
        ),
        Index("idx_wiki_links_source_page_id", "source_page_id"),
        Index("idx_wiki_links_target_page_id", "target_page_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source_page_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("wiki_pages.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_page_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("wiki_pages.id", ondelete="CASCADE"),
        nullable=False,
    )
    relation_type: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'related'")
    )
    extra_meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    source_page: Mapped[WikiPage] = relationship("WikiPage", foreign_keys=[source_page_id])
    target_page: Mapped[WikiPage] = relationship("WikiPage", foreign_keys=[target_page_id])


class WikiSource(Base):
    __tablename__ = "wiki_sources"
    __table_args__ = (
        Index("idx_wiki_sources_page_id", "page_id"),
        Index("idx_wiki_sources_source", "source_type", "source_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    page_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("wiki_pages.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    source_title: Mapped[str | None] = mapped_column(String(255))
    quote_text: Mapped[str | None] = mapped_column(Text)
    extra_meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    page: Mapped[WikiPage] = relationship("WikiPage", back_populates="sources")
