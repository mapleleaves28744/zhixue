from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.quiz import AnswerRecord, MistakeBook, Question, Quiz


class QuizRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_quiz(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        knowledge_id: UUID | None,
        title: str,
        quiz_type: str,
        difficulty: str | None,
    ) -> Quiz:
        quiz = Quiz(
            user_id=user_id,
            course_id=course_id,
            knowledge_id=knowledge_id,
            title=title,
            quiz_type=quiz_type,
            difficulty=difficulty,
            status="generated",
        )
        self.db.add(quiz)
        await self.db.flush()
        return quiz

    async def create_questions(
        self,
        *,
        quiz: Quiz,
        items: Sequence[dict],
    ) -> list[Question]:
        questions: list[Question] = []
        for item in items:
            question = Question(
                quiz_id=quiz.id,
                course_id=quiz.course_id,
                knowledge_id=quiz.knowledge_id,
                question_type=item["question_type"],
                difficulty=item.get("difficulty") or quiz.difficulty,
                question_text=item["question_text"],
                options=item.get("options") or [],
                standard_answer=item["standard_answer"],
                analysis=item.get("analysis"),
                error_tags=item.get("error_tags") or [],
                created_by=item.get("created_by") or "ai",
            )
            self.db.add(question)
            questions.append(question)
        await self.db.flush()
        return questions

    async def list_quizzes(
        self,
        *,
        user_id: UUID,
        course_id: UUID | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Quiz], int]:
        statement = self._user_quiz_statement(user_id=user_id, course_id=course_id)
        total_statement = select(func.count()).select_from(statement.subquery())
        total = await self.db.scalar(total_statement)
        result = await self.db.execute(
            statement.options(selectinload(Quiz.questions))
            .order_by(Quiz.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), int(total or 0)

    async def get_quiz_for_user(self, *, quiz_id: UUID, user_id: UUID) -> Quiz | None:
        result = await self.db.execute(
            select(Quiz)
            .where(Quiz.id == quiz_id, Quiz.user_id == user_id)
            .options(selectinload(Quiz.questions))
        )
        return result.scalar_one_or_none()

    async def create_answer_record(
        self,
        *,
        record: AnswerRecord,
    ) -> AnswerRecord:
        self.db.add(record)
        await self.db.flush()
        return record

    async def create_mistake(self, *, mistake: MistakeBook) -> MistakeBook:
        self.db.add(mistake)
        await self.db.flush()
        return mistake

    async def list_mistakes(
        self,
        *,
        user_id: UUID,
        course_id: UUID | None,
        knowledge_id: UUID | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[MistakeBook], int]:
        statement = select(MistakeBook).where(MistakeBook.user_id == user_id)
        if course_id is not None:
            statement = statement.where(MistakeBook.course_id == course_id)
        if knowledge_id is not None:
            statement = statement.where(MistakeBook.knowledge_id == knowledge_id)
        if status is not None and status != "all":
            statement = statement.where(MistakeBook.status == status)

        total_statement = select(func.count()).select_from(statement.subquery())
        total = await self.db.scalar(total_statement)
        result = await self.db.execute(
            statement.options(
                selectinload(MistakeBook.question),
                selectinload(MistakeBook.answer_record),
            )
            .order_by(MistakeBook.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), int(total or 0)

    def _user_quiz_statement(self, *, user_id: UUID, course_id: UUID | None) -> Select[tuple[Quiz]]:
        statement = select(Quiz).where(Quiz.user_id == user_id)
        if course_id is not None:
            statement = statement.where(Quiz.course_id == course_id)
        return statement
