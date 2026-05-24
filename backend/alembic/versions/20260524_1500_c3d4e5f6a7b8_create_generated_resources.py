"""create generated resources

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generated_resources",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("knowledge_id", UUID(as_uuid=True), sa.ForeignKey("knowledge_points.id", ondelete="SET NULL"), nullable=True),
        sa.Column("wiki_page_id", UUID(as_uuid=True), sa.ForeignKey("wiki_pages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("citations", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("personalized_reason", sa.Text, nullable=True),
        sa.Column("model_name", sa.String(128), nullable=True),
        sa.Column("prompt_version_id", UUID(as_uuid=True), sa.ForeignKey("prompt_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_generated_resources_user_course", "generated_resources", ["user_id", "course_id"])
    op.create_index("idx_generated_resources_knowledge_id", "generated_resources", ["knowledge_id"])
    op.create_index("idx_generated_resources_type", "generated_resources", ["resource_type"])


def downgrade() -> None:
    op.drop_index("idx_generated_resources_type", table_name="generated_resources")
    op.drop_index("idx_generated_resources_knowledge_id", table_name="generated_resources")
    op.drop_index("idx_generated_resources_user_course", table_name="generated_resources")
    op.drop_table("generated_resources")
