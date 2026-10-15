"""Add scoped, auditable learning memory lifecycle and reflection jobs.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e7f8a9b0c1d2"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("student_memories", sa.Column("fact_key", sa.String(255)))
    op.add_column("student_memories", sa.Column("origin", sa.String(32), server_default="legacy", nullable=False))
    op.add_column("student_memories", sa.Column("revision", sa.Integer(), server_default="1", nullable=False))
    op.add_column("student_memories", sa.Column("lifecycle_meta", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.execute("UPDATE student_memories SET lifecycle_meta = '{\"archive_reason\": \"legacy\"}'::jsonb WHERE status = 'archived'")
    op.create_index("uq_student_memories_global_fact_active", "student_memories", ["user_id", "fact_key"], unique=True,
                    postgresql_where=sa.text("course_id IS NULL AND status = 'active' AND fact_key IS NOT NULL"))
    op.create_index("uq_student_memories_course_fact_active", "student_memories", ["user_id", "course_id", "fact_key"], unique=True,
                    postgresql_where=sa.text("course_id IS NOT NULL AND status = 'active' AND fact_key IS NOT NULL"))

    op.add_column("memory_reflection_states", sa.Column("memory_revision", sa.Integer(), server_default="0", nullable=False))
    op.create_index("uq_memory_reflection_states_global", "memory_reflection_states", ["user_id"], unique=True,
                    postgresql_where=sa.text("course_id IS NULL"))

    op.create_table(
        "student_memory_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("student_memories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor", sa.String(32), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("before_snapshot", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("after_snapshot", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("source_refs", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("memory_id", "operation_id", name="uq_student_memory_events_operation"),
    )
    op.create_table(
        "student_memory_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("student_memories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stance", sa.String(16), server_default="support", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("memory_id", "source_type", "source_id", "stance", name="uq_student_memory_evidence_source"),
    )
    op.create_table(
        "memory_reflection_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE")),
        sa.Column("source_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("learning_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("extractor_version", sa.String(32), server_default="v1", nullable=False),
        sa.Column("status", sa.String(32), server_default="pending", nullable=False),
        sa.Column("lease_owner", sa.String(128)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("lease_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("retry_at", sa.DateTime(timezone=True)),
        sa.Column("candidate_payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source_record_id", "extractor_version", name="uq_memory_reflection_jobs_source_version"),
    )
    op.create_index("idx_memory_reflection_jobs_pending", "memory_reflection_jobs", ["status", "retry_at"])


def downgrade() -> None:
    op.drop_index("idx_memory_reflection_jobs_pending", table_name="memory_reflection_jobs")
    op.drop_table("memory_reflection_jobs")
    op.drop_table("student_memory_evidence")
    op.drop_table("student_memory_events")
    op.drop_index("uq_memory_reflection_states_global", table_name="memory_reflection_states")
    op.drop_column("memory_reflection_states", "memory_revision")
    op.drop_index("uq_student_memories_course_fact_active", table_name="student_memories")
    op.drop_index("uq_student_memories_global_fact_active", table_name="student_memories")
    for column in ("lifecycle_meta", "revision", "origin", "fact_key"):
        op.drop_column("student_memories", column)
