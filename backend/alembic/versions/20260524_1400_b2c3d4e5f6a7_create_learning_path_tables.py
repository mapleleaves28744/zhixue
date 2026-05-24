"""create learning path tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learning_paths",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("goal", sa.Text, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("progress", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("strategy_version_id", UUID(as_uuid=True), sa.ForeignKey("evolution_strategies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_learning_paths_user_course", "learning_paths", ["user_id", "course_id"])
    op.create_index("idx_learning_paths_status", "learning_paths", ["status"])

    op.create_table(
        "learning_path_items",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("path_id", UUID(as_uuid=True), sa.ForeignKey("learning_paths.id", ondelete="CASCADE"), nullable=False),
        sa.Column("knowledge_id", UUID(as_uuid=True), sa.ForeignKey("knowledge_points.id", ondelete="SET NULL"), nullable=True),
        sa.Column("wiki_page_id", UUID(as_uuid=True), sa.ForeignKey("wiki_pages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("item_type", sa.String(64), nullable=False, server_default="learn"),
        sa.Column("order_index", sa.Integer, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("estimated_minutes", sa.Integer, nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_learning_path_items_path_id", "learning_path_items", ["path_id"])
    op.create_index("idx_learning_path_items_knowledge_id", "learning_path_items", ["knowledge_id"])
    op.create_index("idx_learning_path_items_status", "learning_path_items", ["status"])


def downgrade() -> None:
    op.drop_index("idx_learning_path_items_status", table_name="learning_path_items")
    op.drop_index("idx_learning_path_items_knowledge_id", table_name="learning_path_items")
    op.drop_index("idx_learning_path_items_path_id", table_name="learning_path_items")
    op.drop_table("learning_path_items")
    op.drop_index("idx_learning_paths_status", table_name="learning_paths")
    op.drop_index("idx_learning_paths_user_course", table_name="learning_paths")
    op.drop_table("learning_paths")
