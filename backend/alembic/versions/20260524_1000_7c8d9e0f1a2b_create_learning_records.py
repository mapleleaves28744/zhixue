"""create_learning_records

Revision ID: 7c8d9e0f1a2b
Revises: 6b7c8d9e0f1a
Create Date: 2026-05-24 10:00:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '7c8d9e0f1a2b'
down_revision: Union[str, None] = '6b7c8d9e0f1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'learning_records',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('course_id', sa.UUID(), nullable=True),
        sa.Column('knowledge_id', sa.UUID(), nullable=True),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('event_source', sa.String(length=64), nullable=True),
        sa.Column('event_payload', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_learning_records_user_id', 'learning_records', ['user_id'], unique=False)
    op.create_index('idx_learning_records_course_id', 'learning_records', ['course_id'], unique=False)
    op.create_index('idx_learning_records_event_type', 'learning_records', ['event_type'], unique=False)
    op.create_index('idx_learning_records_created_at', 'learning_records', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_learning_records_created_at', table_name='learning_records')
    op.drop_index('idx_learning_records_event_type', table_name='learning_records')
    op.drop_index('idx_learning_records_course_id', table_name='learning_records')
    op.drop_index('idx_learning_records_user_id', table_name='learning_records')
    op.drop_table('learning_records')
