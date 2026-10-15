"""Give conversation messages a stable order for context coverage.

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
"""

from alembic import op
import sqlalchemy as sa


revision = "c1d2e3f4a5b6"
down_revision = "b0c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_conversations", sa.Column("next_message_sequence", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("agent_messages", sa.Column("sequence_no", sa.Integer()))
    op.execute("""
        WITH numbered AS (
            SELECT id, row_number() OVER (PARTITION BY conversation_id ORDER BY created_at, id) AS seq
            FROM agent_messages
        )
        UPDATE agent_messages AS message SET sequence_no = numbered.seq
        FROM numbered WHERE message.id = numbered.id
    """)
    op.execute("""
        UPDATE agent_conversations AS conversation
        SET next_message_sequence = COALESCE((
            SELECT max(message.sequence_no) FROM agent_messages AS message
            WHERE message.conversation_id = conversation.id
        ), 0)
    """)
    op.alter_column("agent_messages", "sequence_no", nullable=False)
    op.create_unique_constraint("uq_agent_messages_conversation_sequence", "agent_messages", ["conversation_id", "sequence_no"])


def downgrade() -> None:
    op.drop_constraint("uq_agent_messages_conversation_sequence", "agent_messages", type_="unique")
    op.drop_column("agent_messages", "sequence_no")
    op.drop_column("agent_conversations", "next_message_sequence")
