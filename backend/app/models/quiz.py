from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.knowledge import KnowledgePoint
    from app.models.user import User


class Quiz(Base):
    """一次练习、测验或 AI 生成题组。"""

    __tablename__ = "quizzes"
    __table_args__ = (
        Index("idx_quizzes_user_course", "user_id", "course_id"),
        Index("idx_quizzes_knowledge_id", "knowledge_id"),
        Index("idx_quizzes_type", "quiz_type"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    knowledge_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("knowledge_points.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    quiz_type: Mapped[str] = mapped_column(String(64), nullable=False, server_default=text("'practice'"))
    difficulty: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'generated'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship("User")
    course: Mapped["Course"] = relationship("Course", back_populates="quizzes")
    knowledge: Mapped["KnowledgePoint | None"] = relationship("KnowledgePoint")
    questions: Mapped[list["Question"]] = relationship(
        "Question",
        back_populates="quiz",
        cascade="all, delete-orphan",
    )
    answer_records: Mapped[list["AnswerRecord"]] = relationship(
        "AnswerRecord",
        back_populates="quiz",
    )


class Question(Base):
    """练习题目。"""

    __tablename__ = "questions"
    __table_args__ = (
        Index("idx_questions_quiz_id", "quiz_id"),
        Index("idx_questions_course_id", "course_id"),
        Index("idx_questions_knowledge_id", "knowledge_id"),
        Index("idx_questions_type", "question_type"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    quiz_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=True,
    )
    course_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    knowledge_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("knowledge_points.id", ondelete="SET NULL"),
        nullable=True,
    )
    question_type: Mapped[str] = mapped_column(String(64), nullable=False)
    difficulty: Mapped[str | None] = mapped_column(String(32))
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[Any] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    standard_answer: Mapped[str] = mapped_column(Text, nullable=False)
    analysis: Mapped[str | None] = mapped_column(Text)
    error_tags: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    created_by: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'ai'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    quiz: Mapped["Quiz | None"] = relationship("Quiz", back_populates="questions")
    course: Mapped["Course"] = relationship("Course")
    knowledge: Mapped["KnowledgePoint | None"] = relationship("KnowledgePoint")
    answer_records: Mapped[list["AnswerRecord"]] = relationship(
        "AnswerRecord",
        back_populates="question",
    )
    mistakes: Mapped[list["MistakeBook"]] = relationship(
        "MistakeBook",
        back_populates="question",
    )


class AnswerRecord(Base):
    """学生答题记录和批改结果。"""

    __tablename__ = "answer_records"
    __table_args__ = (
        Index("idx_answer_records_user_id", "user_id"),
        Index("idx_answer_records_quiz_id", "quiz_id"),
        Index("idx_answer_records_question_id", "question_id"),
        Index("idx_answer_records_correct", "is_correct"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    quiz_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="SET NULL"),
        nullable=True,
    )
    question_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    answer_text: Mapped[str | None] = mapped_column(Text)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    feedback: Mapped[str | None] = mapped_column(Text)
    error_tags: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship("User")
    quiz: Mapped["Quiz | None"] = relationship("Quiz", back_populates="answer_records")
    question: Mapped["Question"] = relationship("Question", back_populates="answer_records")
    mistake: Mapped["MistakeBook | None"] = relationship(
        "MistakeBook",
        back_populates="answer_record",
        uselist=False,
    )


class MistakeBook(Base):
    """错题本记录。"""

    __tablename__ = "mistake_books"
    __table_args__ = (
        Index("idx_mistake_books_user_course", "user_id", "course_id"),
        Index("idx_mistake_books_knowledge_id", "knowledge_id"),
        Index("idx_mistake_books_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    knowledge_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("knowledge_points.id", ondelete="SET NULL"),
        nullable=True,
    )
    question_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    answer_record_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("answer_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    error_summary: Mapped[str | None] = mapped_column(Text)
    correction: Mapped[str | None] = mapped_column(Text)
    error_tags: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'unresolved'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship("User")
    course: Mapped["Course"] = relationship("Course")
    knowledge: Mapped["KnowledgePoint | None"] = relationship("KnowledgePoint")
    question: Mapped["Question"] = relationship("Question", back_populates="mistakes")
    answer_record: Mapped["AnswerRecord"] = relationship("AnswerRecord", back_populates="mistake")
