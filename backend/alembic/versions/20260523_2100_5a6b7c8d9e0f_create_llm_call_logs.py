"""create llm call logs

Revision ID: 5a6b7c8d9e0f
Revises: 4f5e6d7c8b9a
Create Date: 2026-05-23 21:00:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "5a6b7c8d9e0f"
down_revision: Union[str, None] = "4f5e6d7c8b9a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_call_logs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("course_id", sa.UUID(), nullable=True),
        sa.Column("agent_run_id", sa.UUID(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("prompt_version_id", sa.UUID(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column(
            "request_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "response_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["prompt_version_id"], ["prompt_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_llm_call_logs_user_course", "llm_call_logs", ["user_id", "course_id"], unique=False)
    op.create_index("idx_llm_call_logs_agent_run", "llm_call_logs", ["agent_run_id"], unique=False)
    op.create_index("idx_llm_call_logs_provider_model", "llm_call_logs", ["provider", "model_name"], unique=False)
    op.create_index("idx_llm_call_logs_status", "llm_call_logs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_llm_call_logs_status", table_name="llm_call_logs")
    op.drop_index("idx_llm_call_logs_provider_model", table_name="llm_call_logs")
    op.drop_index("idx_llm_call_logs_agent_run", table_name="llm_call_logs")
    op.drop_index("idx_llm_call_logs_user_course", table_name="llm_call_logs")
    op.drop_table("llm_call_logs")
