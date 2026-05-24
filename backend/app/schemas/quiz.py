from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


VALID_QUESTION_TYPES = {
    "single_choice",
    "multiple_choice",
    "judge",
    "short_answer",
    "fill_blank",
    "coding",
}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}
VALID_QUIZ_TYPES = {"practice", "diagnosis", "review"}


class QuizGenerateRequest(BaseModel):
    course_id: UUID
    knowledge_id: UUID | None = None
    quiz_type: str = "practice"
    question_types: list[str] = Field(default_factory=lambda: ["single_choice"], min_length=1, max_length=4)
    difficulty: str = "medium"
    count: int = Field(default=5, ge=1, le=20)
    topic: str | None = Field(default=None, max_length=128)

    @field_validator("quiz_type")
    @classmethod
    def validate_quiz_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in VALID_QUIZ_TYPES:
            raise ValueError("quiz_type 只能是 practice / diagnosis / review")
        return normalized

    @field_validator("question_types")
    @classmethod
    def validate_question_types(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().lower() for value in values]
        invalid = [value for value in normalized if value not in VALID_QUESTION_TYPES]
        if invalid:
            raise ValueError("question_types 包含不支持的题型")
        return normalized

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in VALID_DIFFICULTIES:
            raise ValueError("difficulty 只能是 easy / medium / hard")
        return normalized


class QuizSubmitAnswer(BaseModel):
    question_id: UUID
    answer_text: str = Field(default="", max_length=4000)


class QuizSubmitRequest(BaseModel):
    answers: list[QuizSubmitAnswer] = Field(min_length=1)


class QuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    quiz_id: UUID | None
    course_id: UUID
    knowledge_id: UUID | None
    question_type: str
    difficulty: str | None
    question_text: str
    options: list[Any] | dict[str, Any]
    standard_answer: str
    analysis: str | None
    error_tags: list[Any]
    created_by: str
    created_at: datetime | None


class QuizRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    course_id: UUID
    knowledge_id: UUID | None
    title: str
    quiz_type: str
    difficulty: str | None
    status: str
    created_at: datetime | None
    questions: list[QuestionRead] = Field(default_factory=list)


class AnswerRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    quiz_id: UUID | None
    question_id: UUID
    answer_text: str | None
    is_correct: bool | None
    score: Decimal | None
    feedback: str | None
    error_tags: list[Any]
    answered_at: datetime | None
    reviewed_at: datetime | None


class MistakeBookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    course_id: UUID
    knowledge_id: UUID | None
    question_id: UUID
    answer_record_id: UUID
    error_summary: str | None
    correction: str | None
    error_tags: list[Any]
    status: str
    created_at: datetime | None
    updated_at: datetime | None
    question: QuestionRead | None = None
    answer_record: AnswerRecordRead | None = None


class QuizGenerateResponse(BaseModel):
    quiz_id: UUID
    title: str
    questions: list[QuestionRead]
    agent_run_id: UUID | None = None


class QuizSubmitResponse(BaseModel):
    quiz_id: UUID
    total_questions: int
    correct_count: int
    score: float
    records: list[AnswerRecordRead]
    mistakes: list[MistakeBookRead]
