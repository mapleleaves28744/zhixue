"""bound existing active memories

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-06-13
"""

from alembic import op

revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        WITH ranked AS (
          SELECT id,
                 row_number() OVER (
                   PARTITION BY user_id, course_id
                   ORDER BY salience DESC, confidence DESC, updated_at DESC
                 ) AS rn,
                 CASE WHEN course_id IS NULL THEN 10 ELSE 20 END AS capacity
          FROM student_memories
          WHERE status = 'active'
        )
        UPDATE student_memories m
        SET status = 'archived', archived_at = now()
        FROM ranked
        WHERE m.id = ranked.id AND ranked.rn > ranked.capacity
    """)


def downgrade() -> None:
    pass
