"""Persist question order; historical unknown order remains explicitly unknown."""
from alembic import op
import sqlalchemy as sa

revision = "f4a5b6c7d8e9"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("questions", sa.Column("position", sa.Integer(), nullable=True))
    op.create_unique_constraint("uq_questions_quiz_position", "questions", ["quiz_id", "position"])
    op.create_check_constraint("ck_questions_position_positive", "questions", "position IS NULL OR position >= 1")


def downgrade() -> None:
    op.drop_constraint("ck_questions_position_positive", "questions", type_="check")
    op.drop_constraint("uq_questions_quiz_position", "questions", type_="unique")
    op.drop_column("questions", "position")
