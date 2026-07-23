"""set neutral mastery prior

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-07-14
"""

from alembic import op

revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE student_knowledge_mastery ALTER COLUMN mastery_score SET DEFAULT 0.5")
    op.execute("""
        UPDATE student_knowledge_mastery
        SET mastery_score = 0.5,
            evidence_json = evidence_json || '{"confidence": 0.2, "effective_evidence_count": 0, "source": "initial_prior"}'::jsonb
        WHERE mastery_score = 0
          AND attempt_count = 0
          AND ask_count = 0
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE student_knowledge_mastery ALTER COLUMN mastery_score SET DEFAULT 0.0")
