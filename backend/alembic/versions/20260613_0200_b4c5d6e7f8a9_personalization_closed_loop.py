"""personalization memory profile analytics closed loop

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-06-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("student_memories", sa.Column("memory_key", sa.String(255), nullable=True))
    op.add_column("student_memories", sa.Column("status", sa.String(32), server_default=sa.text("'active'"), nullable=False))
    op.add_column("student_memories", sa.Column("salience", sa.Numeric(5, 4), server_default=sa.text("0.5000"), nullable=False))
    op.add_column("student_memories", sa.Column("reinforcement_count", sa.Integer(), server_default=sa.text("1"), nullable=False))
    op.add_column("student_memories", sa.Column("last_reinforced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("student_memories", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("""
        UPDATE student_memories
        SET memory_key = memory_type || ':' || substr(md5(lower(regexp_replace(trim(content), '\\s+', ' ', 'g'))), 1, 24),
            salience = confidence,
            last_reinforced_at = updated_at
    """)
    op.execute("""
        WITH ranked AS (
          SELECT id,
                 row_number() OVER (
                   PARTITION BY user_id, course_id, memory_key
                   ORDER BY confidence DESC, updated_at DESC
                 ) AS rn,
                 count(*) OVER (PARTITION BY user_id, course_id, memory_key) AS cnt
          FROM student_memories
        )
        UPDATE student_memories m
        SET status = CASE WHEN ranked.rn = 1 THEN 'active' ELSE 'archived' END,
            archived_at = CASE WHEN ranked.rn = 1 THEN NULL ELSE now() END,
            reinforcement_count = CASE WHEN ranked.rn = 1 THEN ranked.cnt ELSE 1 END
        FROM ranked WHERE m.id = ranked.id
    """)
    op.alter_column("student_memories", "memory_key", nullable=False)
    op.create_index("idx_student_memories_scope_key", "student_memories", ["user_id", "course_id", "memory_key"])
    op.create_index("idx_student_memories_active_rank", "student_memories", ["user_id", "course_id", "status", "salience"])

    op.create_table(
        "memory_reflection_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_record_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "course_id", name="uq_memory_reflection_states_scope"),
    )
    op.create_table(
        "student_course_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("learning_goal", sa.Text(), nullable=True),
        sa.Column("profile_summary", sa.Text(), nullable=True),
        sa.Column("mastery_snapshot", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("weak_points", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("error_patterns", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("strategy_summary", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("processed_message_ids", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("version_no", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "course_id", name="uq_student_course_profiles_user_course"),
    )
    op.create_index("idx_student_course_profiles_user_course", "student_course_profiles", ["user_id", "course_id"])
    op.create_table(
        "learning_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("page", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_seconds", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_learning_sessions_user_started", "learning_sessions", ["user_id", "started_at"])
    op.create_index("idx_learning_sessions_user_course", "learning_sessions", ["user_id", "course_id"])

    op.add_column("evolution_strategies", sa.Column("materialized_changes", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("evolution_strategies", sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("evolution_strategies", sa.Column("evaluation_status", sa.String(32), server_default=sa.text("'pending'"), nullable=False))
    op.add_column("evolution_strategies", sa.Column("effect_summary", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("evolution_strategies", sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for column in ("evaluated_at", "effect_summary", "evaluation_status", "applied_at", "materialized_changes"):
        op.drop_column("evolution_strategies", column)
    op.drop_index("idx_learning_sessions_user_course", table_name="learning_sessions")
    op.drop_index("idx_learning_sessions_user_started", table_name="learning_sessions")
    op.drop_table("learning_sessions")
    op.drop_index("idx_student_course_profiles_user_course", table_name="student_course_profiles")
    op.drop_table("student_course_profiles")
    op.drop_table("memory_reflection_states")
    op.drop_index("idx_student_memories_active_rank", table_name="student_memories")
    op.drop_index("idx_student_memories_scope_key", table_name="student_memories")
    for column in ("archived_at", "last_reinforced_at", "reinforcement_count", "salience", "status", "memory_key"):
        op.drop_column("student_memories", column)
