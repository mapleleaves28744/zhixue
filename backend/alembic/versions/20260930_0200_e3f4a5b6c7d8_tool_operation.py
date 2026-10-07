"""Bind business operations independently of model tool call IDs."""
from alembic import op
import sqlalchemy as sa

revision = "e3f4a5b6c7d8"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_task_steps", sa.Column("operation_key", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_agent_task_steps_operation", "agent_task_steps", ["task_id", "operation_key"])


def downgrade() -> None:
    op.drop_constraint("uq_agent_task_steps_operation", "agent_task_steps", type_="unique")
    op.drop_column("agent_task_steps", "operation_key")
