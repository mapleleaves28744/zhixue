"""Track generated resource revision lineage.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generated_resources",
        sa.Column("previous_resource_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "generated_resources",
        sa.Column("revision_no", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_foreign_key(
        "fk_generated_resources_previous_resource_id",
        "generated_resources",
        "generated_resources",
        ["previous_resource_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_generated_resources_previous",
        "generated_resources",
        ["previous_resource_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_generated_resources_previous", table_name="generated_resources")
    op.drop_constraint(
        "fk_generated_resources_previous_resource_id",
        "generated_resources",
        type_="foreignkey",
    )
    op.drop_column("generated_resources", "revision_no")
    op.drop_column("generated_resources", "previous_resource_id")
