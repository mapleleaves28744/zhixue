"""align quiz tables with question and mistake records

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-24 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("quizzes", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("quizzes", sa.Column("knowledge_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "quizzes",
        sa.Column("quiz_type", sa.String(length=64), nullable=False, server_default="practice"),
    )
    op.execute("UPDATE quizzes SET user_id = created_by")
    op.execute("UPDATE quizzes SET status = 'generated' WHERE status = 'active'")
    op.alter_column("quizzes", "user_id", nullable=False)
    op.alter_column(
        "quizzes",
        "status",
        existing_type=sa.String(length=32),
        server_default="generated",
        existing_nullable=False,
    )
    op.alter_column(
        "quizzes",
        "difficulty",
        existing_type=sa.String(length=32),
        nullable=True,
        server_default=None,
    )
    op.create_foreign_key(
        "fk_quizzes_user_id_users",
        "quizzes",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_quizzes_knowledge_id_knowledge_points",
        "quizzes",
        "knowledge_points",
        ["knowledge_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("quiz_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=True),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("knowledge_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_points.id", ondelete="SET NULL"), nullable=True),
        sa.Column("question_type", sa.String(length=64), nullable=False),
        sa.Column("difficulty", sa.String(length=32), nullable=True),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("standard_answer", sa.Text(), nullable=False),
        sa.Column("analysis", sa.Text(), nullable=True),
        sa.Column("error_tags", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_by", sa.String(length=32), nullable=False, server_default="ai"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_questions_quiz_id", "questions", ["quiz_id"])
    op.create_index("idx_questions_course_id", "questions", ["course_id"])
    op.create_index("idx_questions_knowledge_id", "questions", ["knowledge_id"])
    op.create_index("idx_questions_type", "questions", ["question_type"])

    op.execute(
        """
        INSERT INTO questions (
            quiz_id, course_id, knowledge_id, question_type, difficulty,
            question_text, options, standard_answer, analysis, error_tags, created_by, created_at
        )
        SELECT
            id, course_id, knowledge_id, question_type, difficulty,
            question_text, COALESCE(options, '[]'::jsonb), correct_answer, explanation,
            '[]'::jsonb, 'ai', created_at
        FROM quizzes
        """
    )

    op.create_table(
        "answer_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quiz_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quizzes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Numeric(5, 2), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("error_tags", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_answer_records_user_id", "answer_records", ["user_id"])
    op.create_index("idx_answer_records_quiz_id", "answer_records", ["quiz_id"])
    op.create_index("idx_answer_records_question_id", "answer_records", ["question_id"])
    op.create_index("idx_answer_records_correct", "answer_records", ["is_correct"])

    op.create_table(
        "mistake_books",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("knowledge_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_points.id", ondelete="SET NULL"), nullable=True),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answer_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("answer_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("correction", sa.Text(), nullable=True),
        sa.Column("error_tags", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="unresolved"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_mistake_books_user_course", "mistake_books", ["user_id", "course_id"])
    op.create_index("idx_mistake_books_knowledge_id", "mistake_books", ["knowledge_id"])
    op.create_index("idx_mistake_books_status", "mistake_books", ["status"])

    op.drop_index("idx_quiz_attempts_quiz_id", table_name="quiz_attempts")
    op.drop_index("idx_quiz_attempts_user_id", table_name="quiz_attempts")
    op.drop_table("quiz_attempts")

    op.drop_index("idx_quizzes_course_id", table_name="quizzes")
    op.drop_index("idx_quizzes_created_by", table_name="quizzes")
    op.create_index("idx_quizzes_user_course", "quizzes", ["user_id", "course_id"])
    op.create_index("idx_quizzes_knowledge_id", "quizzes", ["knowledge_id"])
    op.create_index("idx_quizzes_type", "quizzes", ["quiz_type"])

    for column_name in (
        "created_by",
        "description",
        "question_type",
        "question_text",
        "options",
        "correct_answer",
        "explanation",
        "knowledge_tags",
        "source_material_id",
        "updated_at",
    ):
        op.drop_column("quizzes", column_name)


def downgrade() -> None:
    op.add_column("quizzes", sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("quizzes", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("quizzes", sa.Column("question_type", sa.String(length=32), nullable=True))
    op.add_column("quizzes", sa.Column("question_text", sa.Text(), nullable=True))
    op.add_column("quizzes", sa.Column("options", postgresql.JSONB(), nullable=True))
    op.add_column("quizzes", sa.Column("correct_answer", sa.Text(), nullable=True))
    op.add_column("quizzes", sa.Column("explanation", sa.Text(), nullable=True))
    op.add_column("quizzes", sa.Column("knowledge_tags", postgresql.JSONB(), nullable=True))
    op.add_column("quizzes", sa.Column("source_material_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "quizzes",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.execute(
        """
        UPDATE quizzes q
        SET
            created_by = q.user_id,
            question_type = COALESCE(src.question_type, 'multiple_choice'),
            question_text = COALESCE(src.question_text, q.title),
            options = src.options,
            correct_answer = COALESCE(src.standard_answer, ''),
            explanation = src.analysis,
            knowledge_tags = '[]'::jsonb
        FROM (
            SELECT DISTINCT ON (quiz_id)
                quiz_id, question_type, question_text, options, standard_answer, analysis
            FROM questions
            WHERE quiz_id IS NOT NULL
            ORDER BY quiz_id, created_at
        ) src
        WHERE q.id = src.quiz_id
        """
    )
    op.execute(
        """
        UPDATE quizzes
        SET
            created_by = COALESCE(created_by, user_id),
            question_type = COALESCE(question_type, 'multiple_choice'),
            question_text = COALESCE(question_text, title),
            options = COALESCE(options, '[]'::jsonb),
            correct_answer = COALESCE(correct_answer, ''),
            knowledge_tags = COALESCE(knowledge_tags, '[]'::jsonb)
        """
    )
    op.alter_column("quizzes", "created_by", nullable=False)
    op.alter_column("quizzes", "question_type", nullable=False, server_default="multiple_choice")
    op.alter_column("quizzes", "difficulty", existing_type=sa.String(length=32), nullable=False, server_default="medium")
    op.alter_column("quizzes", "question_text", nullable=False)
    op.alter_column("quizzes", "correct_answer", nullable=False)
    op.alter_column("quizzes", "status", existing_type=sa.String(length=32), server_default="active")
    op.execute("UPDATE quizzes SET status = 'active' WHERE status = 'generated'")

    op.create_foreign_key(
        "quizzes_created_by_fkey",
        "quizzes",
        "users",
        ["created_by"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "quizzes_source_material_id_fkey",
        "quizzes",
        "course_materials",
        ["source_material_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_index("idx_mistake_books_status", table_name="mistake_books")
    op.drop_index("idx_mistake_books_knowledge_id", table_name="mistake_books")
    op.drop_index("idx_mistake_books_user_course", table_name="mistake_books")
    op.drop_table("mistake_books")

    op.drop_index("idx_answer_records_correct", table_name="answer_records")
    op.drop_index("idx_answer_records_question_id", table_name="answer_records")
    op.drop_index("idx_answer_records_quiz_id", table_name="answer_records")
    op.drop_index("idx_answer_records_user_id", table_name="answer_records")
    op.drop_table("answer_records")

    op.create_table(
        "quiz_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quiz_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_answer", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("time_spent_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_quiz_attempts_user_id", "quiz_attempts", ["user_id"])
    op.create_index("idx_quiz_attempts_quiz_id", "quiz_attempts", ["quiz_id"])

    op.drop_index("idx_questions_type", table_name="questions")
    op.drop_index("idx_questions_knowledge_id", table_name="questions")
    op.drop_index("idx_questions_course_id", table_name="questions")
    op.drop_index("idx_questions_quiz_id", table_name="questions")
    op.drop_table("questions")

    op.drop_index("idx_quizzes_type", table_name="quizzes")
    op.drop_index("idx_quizzes_knowledge_id", table_name="quizzes")
    op.drop_index("idx_quizzes_user_course", table_name="quizzes")
    op.drop_constraint("fk_quizzes_knowledge_id_knowledge_points", "quizzes", type_="foreignkey")
    op.drop_constraint("fk_quizzes_user_id_users", "quizzes", type_="foreignkey")
    op.drop_column("quizzes", "quiz_type")
    op.drop_column("quizzes", "knowledge_id")
    op.drop_column("quizzes", "user_id")
    op.create_index("idx_quizzes_course_id", "quizzes", ["course_id"])
    op.create_index("idx_quizzes_created_by", "quizzes", ["created_by"])
