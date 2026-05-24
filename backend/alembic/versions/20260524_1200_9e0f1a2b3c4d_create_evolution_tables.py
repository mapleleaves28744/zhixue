"""create_evolution_tables

Revision ID: 9e0f1a2b3c4d
Revises: 8d9e0f1a2b3c
Create Date: 2026-05-24 12:00:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '9e0f1a2b3c4d'
down_revision: Union[str, None] = '8d9e0f1a2b3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'evolution_strategies',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('course_id', sa.UUID(), nullable=True),
        sa.Column('strategy_type', sa.String(length=64), nullable=False),
        sa.Column('before_value', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('after_value', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=32), server_default=sa.text("'draft'"), nullable=False),
        sa.Column('risk_level', sa.String(length=32), server_default=sa.text("'low'"), nullable=False),
        sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('previous_strategy_id', sa.UUID(), nullable=True),
        sa.Column('version_no', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['previous_strategy_id'], ['evolution_strategies.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_evolution_strategies_user_course', 'evolution_strategies', ['user_id', 'course_id'], unique=False)
    op.create_index('idx_evolution_strategies_status', 'evolution_strategies', ['status'], unique=False)

    op.create_table(
        'evolution_events',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('course_id', sa.UUID(), nullable=True),
        sa.Column('trigger_type', sa.String(length=64), server_default=sa.text("'manual'"), nullable=False),
        sa.Column('focus', sa.String(length=256), nullable=False),
        sa.Column('input_snapshot', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('strategies_generated', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('status', sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_evolution_events_user_course', 'evolution_events', ['user_id', 'course_id'], unique=False)
    op.create_index('idx_evolution_events_status', 'evolution_events', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_evolution_events_status', table_name='evolution_events')
    op.drop_index('idx_evolution_events_user_course', table_name='evolution_events')
    op.drop_table('evolution_events')
    op.drop_index('idx_evolution_strategies_status', table_name='evolution_strategies')
    op.drop_index('idx_evolution_strategies_user_course', table_name='evolution_strategies')
    op.drop_table('evolution_strategies')
