"""Make Agent message submission idempotent per conversation.

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a9b0c1d2e3f4"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_messages", sa.Column("client_request_id", postgresql.UUID(as_uuid=True)))
    op.create_index("uq_agent_messages_conversation_request", "agent_messages", ["conversation_id", "client_request_id"],
                    unique=True, postgresql_where=sa.text("client_request_id IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("uq_agent_messages_conversation_request", table_name="agent_messages")
    op.drop_column("agent_messages", "client_request_id")
