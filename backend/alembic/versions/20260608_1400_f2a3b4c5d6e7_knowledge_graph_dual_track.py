"""knowledge graph dual-track: relations, mastery, wiki knowledge_id

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-06-08 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "f2a3b4c5d6e7"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_relations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("source_knowledge_id", sa.UUID(), nullable=False),
        sa.Column("target_knowledge_id", sa.UUID(), nullable=False),
        sa.Column("relation_type", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=32), server_default="public", nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("created_by", sa.String(length=32), server_default="seed", nullable=False),
        sa.Column(
            "extra_meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_knowledge_id"], ["knowledge_points.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_knowledge_id"], ["knowledge_points.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "course_id",
            "source_knowledge_id",
            "target_knowledge_id",
            "relation_type",
            "scope",
            name="uq_knowledge_relations_edge",
        ),
    )
    op.create_index("idx_knowledge_relations_course_id", "knowledge_relations", ["course_id"])
    op.create_index("idx_knowledge_relations_source", "knowledge_relations", ["source_knowledge_id"])
    op.create_index("idx_knowledge_relations_target", "knowledge_relations", ["target_knowledge_id"])
    op.create_index("idx_knowledge_relations_scope", "knowledge_relations", ["scope"])

    op.create_table(
        "student_knowledge_mastery",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("knowledge_id", sa.UUID(), nullable=False),
        sa.Column("mastery_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("stability", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("correct_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("ask_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_practiced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_asked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "evidence_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_id"], ["knowledge_points.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "course_id", "knowledge_id", name="uq_student_knowledge_mastery"),
    )
    op.create_index("idx_skm_user_course", "student_knowledge_mastery", ["user_id", "course_id"])
    op.create_index("idx_skm_knowledge_id", "student_knowledge_mastery", ["knowledge_id"])

    op.add_column("wiki_pages", sa.Column("knowledge_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_wiki_pages_knowledge_id",
        "wiki_pages",
        "knowledge_points",
        ["knowledge_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_wiki_pages_knowledge_id", "wiki_pages", ["knowledge_id"])


def downgrade() -> None:
    op.drop_index("idx_wiki_pages_knowledge_id", table_name="wiki_pages")
    op.drop_constraint("fk_wiki_pages_knowledge_id", "wiki_pages", type_="foreignkey")
    op.drop_column("wiki_pages", "knowledge_id")
    op.drop_index("idx_skm_knowledge_id", table_name="student_knowledge_mastery")
    op.drop_index("idx_skm_user_course", table_name="student_knowledge_mastery")
    op.drop_table("student_knowledge_mastery")
    op.drop_index("idx_knowledge_relations_scope", table_name="knowledge_relations")
    op.drop_index("idx_knowledge_relations_target", table_name="knowledge_relations")
    op.drop_index("idx_knowledge_relations_source", table_name="knowledge_relations")
    op.drop_index("idx_knowledge_relations_course_id", table_name="knowledge_relations")
    op.drop_table("knowledge_relations")
