"""create_knowledge_points_and_document_chunks

Revision ID: 3a1b2c3d4e5f
Revises: 2e0e8b4f9b1c
Create Date: 2026-05-23 18:00:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql


revision: str = "3a1b2c3d4e5f"
down_revision: Union[str, None] = "2e0e8b4f9b1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_vector_extension() -> bool:
    """Check if pgvector extension is available."""
    conn = op.get_bind()
    try:
        result = conn.execute(text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'"))
        return result.scalar() is not None
    except Exception:
        return False


def upgrade() -> None:
    has_vector = _has_vector_extension()

    if has_vector:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "knowledge_points",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("chapter", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.String(length=32), nullable=True),
        sa.Column("importance", sa.String(length=32), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "extra_meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["knowledge_points.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_id", "name", name="uq_knowledge_points_course_name"),
    )
    op.create_index("idx_knowledge_points_course_id", "knowledge_points", ["course_id"], unique=False)
    op.create_index("idx_knowledge_points_parent_id", "knowledge_points", ["parent_id"], unique=False)
    op.create_index("idx_knowledge_points_name", "knowledge_points", ["name"], unique=False)

    if has_vector:
        op.execute(
            "CREATE TABLE document_chunks ("
            "  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),"
            "  material_id uuid NOT NULL REFERENCES course_materials(id) ON DELETE CASCADE,"
            "  course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,"
            "  knowledge_id uuid REFERENCES knowledge_points(id) ON DELETE SET NULL,"
            "  chunk_index integer NOT NULL,"
            "  content text NOT NULL,"
            "  token_count integer,"
            "  page_no integer,"
            "  source_title varchar(255),"
            "  embedding vector(1024),"
            "  extra_meta jsonb NOT NULL DEFAULT '{}'::jsonb,"
            "  created_at timestamptz NOT NULL DEFAULT now()"
            ")"
        )
    else:
        op.create_table(
            "document_chunks",
            sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("material_id", sa.UUID(), nullable=False),
            sa.Column("course_id", sa.UUID(), nullable=False),
            sa.Column("knowledge_id", sa.UUID(), nullable=True),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("token_count", sa.Integer(), nullable=True),
            sa.Column("page_no", sa.Integer(), nullable=True),
            sa.Column("source_title", sa.String(length=255), nullable=True),
            sa.Column("embedding", sa.Text(), nullable=True),
            sa.Column(
                "extra_meta",
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'{}'::jsonb"),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["material_id"], ["course_materials.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["knowledge_id"], ["knowledge_points.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    op.create_index("idx_document_chunks_material_id", "document_chunks", ["material_id"], unique=False)
    op.create_index("idx_document_chunks_course_id", "document_chunks", ["course_id"], unique=False)
    op.create_index("idx_document_chunks_knowledge_id", "document_chunks", ["knowledge_id"], unique=False)
    op.create_index("idx_document_chunks_chunk_index", "document_chunks", ["chunk_index"], unique=False)

    if has_vector:
        op.execute(
            "CREATE INDEX idx_document_chunks_embedding_hnsw "
            "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
        )


def downgrade() -> None:
    op.drop_index("idx_document_chunks_chunk_index", table_name="document_chunks")
    op.drop_index("idx_document_chunks_knowledge_id", table_name="document_chunks")
    op.drop_index("idx_document_chunks_course_id", table_name="document_chunks")
    op.drop_index("idx_document_chunks_material_id", table_name="document_chunks")
    try:
        op.drop_index("idx_document_chunks_embedding_hnsw", table_name="document_chunks")
    except Exception:
        pass
    op.drop_table("document_chunks")
    op.drop_index("idx_knowledge_points_name", table_name="knowledge_points")
    op.drop_index("idx_knowledge_points_parent_id", table_name="knowledge_points")
    op.drop_index("idx_knowledge_points_course_id", table_name="knowledge_points")
    op.drop_table("knowledge_points")
