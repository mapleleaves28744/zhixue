"""add langgraph agent runtime persistence

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-06-07 02:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "d0e1f2a3b4c5"
down_revision: str | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_conversations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("course_id", sa.UUID(), nullable=True),
        sa.Column("thread_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), server_default=sa.text("'新对话'"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'active'"), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("extra_meta", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("thread_id", name="uq_agent_conversations_thread_id"),
    )
    op.create_index("idx_agent_conversations_user_course", "agent_conversations", ["user_id", "course_id"])
    op.create_index("idx_agent_conversations_user_updated", "agent_conversations", ["user_id", "updated_at"])

    op.add_column("agent_tasks", sa.Column("conversation_id", sa.UUID(), nullable=True))
    op.add_column("agent_tasks", sa.Column("thread_id", sa.String(length=128), nullable=True))
    op.add_column("agent_tasks", sa.Column("graph_version", sa.String(length=32), server_default=sa.text("'langgraph-1.0'"), nullable=False))
    op.add_column("agent_tasks", sa.Column("runtime_mode", sa.String(length=32), server_default=sa.text("'langgraph'"), nullable=False))
    op.add_column("agent_tasks", sa.Column("iteration_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("agent_tasks", sa.Column("tool_call_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("agent_tasks", sa.Column("replan_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("agent_tasks", sa.Column("checkpoint_id", sa.String(length=255), nullable=True))
    op.add_column("agent_tasks", sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_agent_tasks_conversation_id", "agent_tasks", "agent_conversations", ["conversation_id"], ["id"], ondelete="SET NULL")
    op.create_index("idx_agent_tasks_conversation", "agent_tasks", ["conversation_id"])
    op.create_index("idx_agent_tasks_thread_id", "agent_tasks", ["thread_id"])
    op.drop_constraint("ck_agent_tasks_status", "agent_tasks", type_="check")
    op.create_check_constraint(
        "ck_agent_tasks_status",
        "agent_tasks",
        "status IN ('draft','planned','queued','waiting_confirmation','running','succeeded','failed','cancelled')",
    )

    op.add_column("agent_task_steps", sa.Column("tool_call_id", sa.String(length=128), nullable=True))
    op.add_column("agent_task_steps", sa.Column("parent_step_id", sa.UUID(), nullable=True))
    op.add_column("agent_task_steps", sa.Column("iteration_no", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("agent_task_steps", sa.Column("node_name", sa.String(length=128), nullable=True))
    op.add_column("agent_task_steps", sa.Column("decision_summary", sa.Text(), nullable=True))
    op.create_foreign_key("fk_agent_task_steps_parent_step_id", "agent_task_steps", "agent_task_steps", ["parent_step_id"], ["id"], ondelete="SET NULL")
    op.create_index("idx_agent_task_steps_tool_call_id", "agent_task_steps", ["tool_call_id"])

    op.create_table(
        "agent_messages",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("message_type", sa.String(length=64), server_default=sa.text("'text'"), nullable=False),
        sa.Column("content", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_agent_messages_conversation_created", "agent_messages", ["conversation_id", "created_at"])
    op.create_index("idx_agent_messages_task_id", "agent_messages", ["task_id"])
    op.create_index("idx_agent_messages_user_id", "agent_messages", ["user_id"])

    op.create_table(
        "agent_task_events",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "sequence_no", name="uq_agent_task_events_task_sequence"),
    )
    op.create_index("idx_agent_task_events_conversation", "agent_task_events", ["conversation_id"])
    op.create_index("idx_agent_task_events_task_created", "agent_task_events", ["task_id", "created_at"])

    op.create_table("checkpoint_migrations", sa.Column("v", sa.Integer(), primary_key=True))
    op.create_table(
        "checkpoints",
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("checkpoint_ns", sa.Text(), server_default="", nullable=False),
        sa.Column("checkpoint_id", sa.Text(), nullable=False),
        sa.Column("parent_checkpoint_id", sa.Text()),
        sa.Column("type", sa.Text()),
        sa.Column("checkpoint", postgresql.JSONB(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.PrimaryKeyConstraint("thread_id", "checkpoint_ns", "checkpoint_id"),
    )
    op.create_table(
        "checkpoint_blobs",
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("checkpoint_ns", sa.Text(), server_default="", nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("blob", sa.LargeBinary(), nullable=True),
        sa.PrimaryKeyConstraint("thread_id", "checkpoint_ns", "channel", "version"),
    )
    op.create_table(
        "checkpoint_writes",
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("checkpoint_ns", sa.Text(), server_default="", nullable=False),
        sa.Column("checkpoint_id", sa.Text(), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("type", sa.Text()),
        sa.Column("blob", sa.LargeBinary(), nullable=False),
        sa.Column("task_path", sa.Text(), server_default="", nullable=False),
        sa.PrimaryKeyConstraint("thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "idx"),
    )
    op.create_index("checkpoints_thread_id_idx", "checkpoints", ["thread_id"])
    op.create_index("checkpoint_blobs_thread_id_idx", "checkpoint_blobs", ["thread_id"])
    op.create_index("checkpoint_writes_thread_id_idx", "checkpoint_writes", ["thread_id"])
    op.execute(sa.text("INSERT INTO checkpoint_migrations (v) SELECT generate_series(0, 9)"))


def downgrade() -> None:
    op.drop_index("checkpoint_writes_thread_id_idx", table_name="checkpoint_writes")
    op.drop_index("checkpoint_blobs_thread_id_idx", table_name="checkpoint_blobs")
    op.drop_index("checkpoints_thread_id_idx", table_name="checkpoints")
    op.drop_table("checkpoint_writes")
    op.drop_table("checkpoint_blobs")
    op.drop_table("checkpoints")
    op.drop_table("checkpoint_migrations")
    op.drop_index("idx_agent_task_events_task_created", table_name="agent_task_events")
    op.drop_index("idx_agent_task_events_conversation", table_name="agent_task_events")
    op.drop_table("agent_task_events")
    op.drop_index("idx_agent_messages_user_id", table_name="agent_messages")
    op.drop_index("idx_agent_messages_task_id", table_name="agent_messages")
    op.drop_index("idx_agent_messages_conversation_created", table_name="agent_messages")
    op.drop_table("agent_messages")
    op.drop_index("idx_agent_task_steps_tool_call_id", table_name="agent_task_steps")
    op.drop_constraint("fk_agent_task_steps_parent_step_id", "agent_task_steps", type_="foreignkey")
    for column in ("decision_summary", "node_name", "iteration_no", "parent_step_id", "tool_call_id"):
        op.drop_column("agent_task_steps", column)
    op.drop_index("idx_agent_tasks_thread_id", table_name="agent_tasks")
    op.drop_index("idx_agent_tasks_conversation", table_name="agent_tasks")
    op.drop_constraint("ck_agent_tasks_status", "agent_tasks", type_="check")
    op.create_check_constraint(
        "ck_agent_tasks_status",
        "agent_tasks",
        "status IN ('draft','planned','waiting_confirmation','running','succeeded','failed','cancelled')",
    )
    op.drop_constraint("fk_agent_tasks_conversation_id", "agent_tasks", type_="foreignkey")
    for column in (
        "last_event_at",
        "checkpoint_id",
        "replan_count",
        "tool_call_count",
        "iteration_count",
        "runtime_mode",
        "graph_version",
        "thread_id",
        "conversation_id",
    ):
        op.drop_column("agent_tasks", column)
    op.drop_index("idx_agent_conversations_user_updated", table_name="agent_conversations")
    op.drop_index("idx_agent_conversations_user_course", table_name="agent_conversations")
    op.drop_table("agent_conversations")
