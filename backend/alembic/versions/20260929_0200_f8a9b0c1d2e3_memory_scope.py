"""Preserve the original scope of memory rows after course deletion.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
"""

from alembic import op


revision = "f8a9b0c1d2e3"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE student_memories
        SET lifecycle_meta = lifecycle_meta ||
            jsonb_build_object('scope', CASE WHEN course_id IS NULL THEN 'global' ELSE 'course' END)
        WHERE NOT (lifecycle_meta ? 'scope')
    """)


def downgrade() -> None:
    op.execute("UPDATE student_memories SET lifecycle_meta = lifecycle_meta - 'scope'")
