"""add_public_kb_hybrid_indexes

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-06-06 18:00:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_document_chunks_extra_meta_gin "
        "ON document_chunks USING gin (extra_meta jsonb_path_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_document_chunks_content_trgm "
        "ON document_chunks USING gin (content gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_document_chunks_chapter_id_expr "
        "ON document_chunks ((extra_meta->>'chapter_id'))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_document_chunks_source_id_expr "
        "ON document_chunks ((extra_meta->>'source_id'))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_document_chunks_chunk_type_expr "
        "ON document_chunks ((extra_meta->>'chunk_type'))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_document_chunks_chunk_type_expr")
    op.execute("DROP INDEX IF EXISTS idx_document_chunks_source_id_expr")
    op.execute("DROP INDEX IF EXISTS idx_document_chunks_chapter_id_expr")
    op.execute("DROP INDEX IF EXISTS idx_document_chunks_content_trgm")
    op.execute("DROP INDEX IF EXISTS idx_document_chunks_extra_meta_gin")
