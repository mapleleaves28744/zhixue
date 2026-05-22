"""create_course_materials

Revision ID: 2e0e8b4f9b1c
Revises: 6caea9718aa3
Create Date: 2026-05-22 14:00:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "2e0e8b4f9b1c"
down_revision: Union[str, None] = "6caea9718aa3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "course_materials",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("uploaded_by", sa.UUID(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("file_size", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("parse_status", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column("text_hash", sa.String(length=128), nullable=True),
        sa.Column(
            "extra_meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_course_materials_course_id", "course_materials", ["course_id"], unique=False)
    op.create_index("idx_course_materials_parse_status", "course_materials", ["parse_status"], unique=False)
    op.create_index("idx_course_materials_uploaded_by", "course_materials", ["uploaded_by"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_course_materials_uploaded_by", table_name="course_materials")
    op.drop_index("idx_course_materials_parse_status", table_name="course_materials")
    op.drop_index("idx_course_materials_course_id", table_name="course_materials")
    op.drop_table("course_materials")
