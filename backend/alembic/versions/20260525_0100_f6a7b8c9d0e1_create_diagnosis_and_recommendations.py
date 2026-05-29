"""create diagnosis reports and recommendations

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-25 01:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "diagnosis_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_type", sa.String(length=64), nullable=False, server_default="practice"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("mastery_result", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("weak_points", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("error_patterns", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("recommended_actions", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("generated_by_agent_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_diagnosis_reports_user_course", "diagnosis_reports", ["user_id", "course_id"])
    op.create_index("idx_diagnosis_reports_type", "diagnosis_reports", ["report_type"])
    op.create_index("idx_diagnosis_reports_created_at", "diagnosis_reports", ["created_at"])

    op.create_table(
        "recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recommendation_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("strategy_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evolution_strategies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_recommendations_user_course", "recommendations", ["user_id", "course_id"])
    op.create_index("idx_recommendations_type", "recommendations", ["recommendation_type"])
    op.create_index("idx_recommendations_status", "recommendations", ["status"])
    op.create_index("idx_recommendations_priority", "recommendations", ["priority"])


def downgrade() -> None:
    op.drop_index("idx_recommendations_priority", table_name="recommendations")
    op.drop_index("idx_recommendations_status", table_name="recommendations")
    op.drop_index("idx_recommendations_type", table_name="recommendations")
    op.drop_index("idx_recommendations_user_course", table_name="recommendations")
    op.drop_table("recommendations")

    op.drop_index("idx_diagnosis_reports_created_at", table_name="diagnosis_reports")
    op.drop_index("idx_diagnosis_reports_type", table_name="diagnosis_reports")
    op.drop_index("idx_diagnosis_reports_user_course", table_name="diagnosis_reports")
    op.drop_table("diagnosis_reports")
