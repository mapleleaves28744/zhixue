"""Track Tutor request claims and completed responses.

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b0c1d2e3f4a5"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tutor_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(32), server_default="running", nullable=False),
        sa.Column("lease_owner", sa.String(64)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("lease_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("response_payload", postgresql.JSONB()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("conversation_id", "client_request_id", name="uq_tutor_requests_conversation_client"),
    )
    op.create_index("idx_tutor_requests_user_status", "tutor_requests", ["user_id", "status"])


def downgrade() -> None:
    op.drop_index("idx_tutor_requests_user_status", table_name="tutor_requests")
    op.drop_table("tutor_requests")
