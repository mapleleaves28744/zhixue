"""create wiki tables

Revision ID: 4f5e6d7c8b9a
Revises: 3a1b2c3d4e5f
Create Date: 2026-05-23 20:00:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql


revision: str = "4f5e6d7c8b9a"
down_revision: Union[str, None] = "3a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # wiki_pages
    op.create_table(
        "wiki_pages",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'active'"), nullable=False),
        sa.Column("current_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "extra_meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_id", "owner_id", "slug", name="uq_wiki_pages_course_owner_slug"),
    )
    op.create_index("idx_wiki_pages_course_id", "wiki_pages", ["course_id"], unique=False)
    op.create_index("idx_wiki_pages_owner_id", "wiki_pages", ["owner_id"], unique=False)
    op.create_index("idx_wiki_pages_status", "wiki_pages", ["status"], unique=False)

    # wiki_page_versions
    op.create_table(
        "wiki_page_versions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("page_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("change_message", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["page_id"], ["wiki_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("page_id", "version_number", name="uq_wiki_page_versions_page_ver"),
    )
    op.create_index("idx_wiki_page_versions_page_id", "wiki_page_versions", ["page_id"], unique=False)

    # wiki_links
    op.create_table(
        "wiki_links",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_page_id", sa.UUID(), nullable=False),
        sa.Column("target_page_id", sa.UUID(), nullable=False),
        sa.Column("relation_type", sa.String(length=64), server_default=sa.text("'related'"), nullable=False),
        sa.Column(
            "extra_meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_page_id"], ["wiki_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_page_id"], ["wiki_pages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_page_id", "target_page_id", "relation_type",
            name="uq_wiki_links_source_target_type",
        ),
    )
    op.create_index("idx_wiki_links_source_page_id", "wiki_links", ["source_page_id"], unique=False)
    op.create_index("idx_wiki_links_target_page_id", "wiki_links", ["target_page_id"], unique=False)

    # wiki_sources
    op.create_table(
        "wiki_sources",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("page_id", sa.UUID(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("source_title", sa.String(length=255), nullable=True),
        sa.Column("quote_text", sa.Text(), nullable=True),
        sa.Column(
            "extra_meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["page_id"], ["wiki_pages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_wiki_sources_page_id", "wiki_sources", ["page_id"], unique=False)
    op.create_index("idx_wiki_sources_source", "wiki_sources", ["source_type", "source_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_wiki_sources_source", table_name="wiki_sources")
    op.drop_index("idx_wiki_sources_page_id", table_name="wiki_sources")
    op.drop_table("wiki_sources")

    op.drop_index("idx_wiki_links_target_page_id", table_name="wiki_links")
    op.drop_index("idx_wiki_links_source_page_id", table_name="wiki_links")
    op.drop_table("wiki_links")

    op.drop_index("idx_wiki_page_versions_page_id", table_name="wiki_page_versions")
    op.drop_table("wiki_page_versions")

    op.drop_index("idx_wiki_pages_status", table_name="wiki_pages")
    op.drop_index("idx_wiki_pages_owner_id", table_name="wiki_pages")
    op.drop_index("idx_wiki_pages_course_id", table_name="wiki_pages")
    op.drop_table("wiki_pages")
