"""add owner and scope to knowledge points

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-25 02:00:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_points", sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "knowledge_points",
        sa.Column("scope", sa.String(length=32), server_default=sa.text("'personal'"), nullable=False),
    )

    op.execute(
        """
        UPDATE knowledge_points AS kp
        SET owner_id = c.owner_id,
            scope = CASE
                WHEN c.visibility = 'public_template' THEN 'public'
                ELSE 'personal'
            END
        FROM courses AS c
        WHERE kp.course_id = c.id
        """
    )

    op.alter_column("knowledge_points", "owner_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.create_foreign_key(
        "fk_knowledge_points_owner_id_users",
        "knowledge_points",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("uq_knowledge_points_course_name", "knowledge_points", type_="unique")
    op.create_unique_constraint(
        "uq_knowledge_points_course_owner_name",
        "knowledge_points",
        ["course_id", "owner_id", "name"],
    )
    op.create_index("idx_knowledge_points_owner_id", "knowledge_points", ["owner_id"], unique=False)
    op.create_index("idx_knowledge_points_scope", "knowledge_points", ["scope"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_knowledge_points_scope", table_name="knowledge_points")
    op.drop_index("idx_knowledge_points_owner_id", table_name="knowledge_points")
    op.drop_constraint("uq_knowledge_points_course_owner_name", "knowledge_points", type_="unique")

    # Downgrading to old course/name uniqueness keeps the course owner's baseline
    # points and drops only student overlay duplicates.
    op.execute(
        """
        DELETE FROM knowledge_points AS kp
        USING courses AS c
        WHERE kp.course_id = c.id
          AND kp.owner_id <> c.owner_id
        """
    )

    op.create_unique_constraint(
        "uq_knowledge_points_course_name",
        "knowledge_points",
        ["course_id", "name"],
    )
    op.drop_constraint("fk_knowledge_points_owner_id_users", "knowledge_points", type_="foreignkey")
    op.drop_column("knowledge_points", "scope")
    op.drop_column("knowledge_points", "owner_id")
