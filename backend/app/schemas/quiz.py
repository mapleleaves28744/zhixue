from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class QuizGenerateRequest(BaseModel):
    course_id: UUID
    topic: str
    count: int = 5
    difficulty: str = "medium"


class QuizSubmitRequest(BaseModel):
    quiz_id: UUID
    user_answer: str
    time_spent_seconds: int | None = None


class QuizRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_id: UUID
    created_by: UUID
    title: str
    description: str | None
    question_type: str
    difficulty: str
    question_text: str
    options: dict | None
    correct_answer: str
    explanation: str | None
    knowledge_tags: Any
    status: str
    created_at: datetime | None
    updated_at: datetime | None


class QuizAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    quiz_id: UUID
    user_answer: str
    is_correct: bool
    time_spent_seconds: int | None
    created_at: datetime | None


class QuizAttemptWithQuiz(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    quiz_id: UUID
    user_answer: str
    is_correct: bool
    time_spent_seconds: int | None
    created_at: datetime | None
    quiz: QuizRead | None = None
