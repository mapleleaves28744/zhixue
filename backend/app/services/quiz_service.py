from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.course import Course
from app.models.knowledge import KnowledgePoint
from app.models.quiz import AnswerRecord, MistakeBook, Question, Quiz
from app.models.user import User
from app.repositories.course_repository import CourseRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.quiz_repository import QuizRepository
from app.schemas.quiz import (
    AnswerRecordRead,
    MistakeBookRead,
    QuestionRead,
    QuizGenerateRequest,
    QuizGenerateResponse,
    QuizRead,
    QuizSubmitRequest,
    QuizSubmitResponse,
)
from app.services.agent_service import AgentService
from app.services.course_service import CourseService
from app.services.learning_record_service import LearningRecordService


class QuizService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.courses = CourseRepository(db)
        self.knowledge = KnowledgeRepository(db)
        self.quizzes = QuizRepository(db)

    async def generate_quiz(
        self,
        *,
        payload: QuizGenerateRequest,
        current_user: User,
    ) -> QuizGenerateResponse:
        course = await self._get_accessible_course(payload.course_id, current_user)
        knowledge = await self._get_knowledge(payload.knowledge_id, course, current_user)
        topic = self._topic(payload.topic, knowledge, course)

        result = await AgentService(self.db).run_task(
            task_type="generate_quiz",
            user_id=current_user.id,
            course_id=course.id,
            params={
                "knowledge_id": str(knowledge.id) if knowledge else None,
                "knowledge_name": topic,
                "knowledge_description": knowledge.description if knowledge else "",
                "question_types": payload.question_types,
                "difficulty": payload.difficulty,
                "count": payload.count,
                "quiz_type": payload.quiz_type,
            },
        )
        if not result.success:
            raise BusinessException(
                code=ErrorCode.AGENT_RUN_FAILED,
                detail=result.message,
                status_code=500,
            )

        question_items = self._normalize_agent_questions(
            result.data.get("questions"),
            topic=topic,
            count=payload.count,
            question_types=payload.question_types,
            difficulty=payload.difficulty,
        )
        quiz = await self.quizzes.create_quiz(
            user_id=current_user.id,
            course_id=course.id,
            knowledge_id=knowledge.id if knowledge else None,
            title=str(result.data.get("title") or f"{topic}练习")[:255],
            quiz_type=payload.quiz_type,
            difficulty=payload.difficulty,
        )
        questions = await self.quizzes.create_questions(quiz=quiz, items=question_items)
        await self.db.commit()
        await self.db.refresh(quiz)
        for question in questions:
            await self.db.refresh(question)

        return QuizGenerateResponse(
            quiz_id=quiz.id,
            title=quiz.title,
            questions=[QuestionRead.model_validate(question) for question in questions],
            agent_run_id=self._uuid(result.data.get("agent_run_id")),
        )

    async def list_quizzes(
        self,
        *,
        current_user: User,
        course_id: UUID | None,
        page: int,
        page_size: int,
    ) -> tuple[list[QuizRead], int]:
        if course_id is not None:
            await self._get_accessible_course(course_id, current_user)
        items, total = await self.quizzes.list_quizzes(
            user_id=current_user.id,
            course_id=course_id,
            page=page,
            page_size=page_size,
        )
        return [QuizRead.model_validate(item) for item in items], total

    async def get_quiz(
        self,
        *,
        quiz_id: UUID,
        current_user: User,
    ) -> QuizRead:
        quiz = await self._get_owned_quiz(quiz_id, current_user.id)
        return QuizRead.model_validate(quiz)

    async def submit_answers(
        self,
        *,
        quiz_id: UUID,
        payload: QuizSubmitRequest,
        current_user: User,
    ) -> QuizSubmitResponse:
        quiz = await self._get_owned_quiz(quiz_id, current_user.id)
        questions_by_id = {question.id: question for question in quiz.questions}
        if not questions_by_id:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="当前练习没有可提交的题目",
                status_code=400,
            )

        records: list[AnswerRecord] = []
        mistakes: list[MistakeBook] = []
        for answer in payload.answers:
            question = questions_by_id.get(answer.question_id)
            if question is None:
                raise BusinessException(
                    code=ErrorCode.NOT_FOUND,
                    detail="题目不存在",
                    status_code=404,
                )
            record, mistake = await self._grade_and_record(
                user_id=current_user.id,
                quiz=quiz,
                question=question,
                answer_text=answer.answer_text,
            )
            records.append(record)
            if mistake is not None:
                mistakes.append(mistake)

        quiz.status = "submitted"
        await LearningRecordService(self.db).record_event(
            user_id=current_user.id,
            course_id=quiz.course_id,
            knowledge_id=quiz.knowledge_id,
            event_type="quiz_submit",
            event_source="quiz",
            event_payload={
                "quiz_id": str(quiz.id),
                "submitted_count": len(records),
                "correct_count": sum(1 for record in records if record.is_correct),
                "mistake_count": len(mistakes),
            },
            commit=False,
        )
        await self.db.commit()
        await self.db.refresh(quiz)
        for record in records:
            await self.db.refresh(record)
        for mistake in mistakes:
            await self.db.refresh(mistake)

        correct_count = sum(1 for record in records if record.is_correct)
        score = round((correct_count / len(records)) * 100, 2) if records else 0.0
        return QuizSubmitResponse(
            quiz_id=quiz.id,
            total_questions=len(records),
            correct_count=correct_count,
            score=score,
            records=[AnswerRecordRead.model_validate(record) for record in records],
            mistakes=[MistakeBookRead.model_validate(mistake) for mistake in mistakes],
        )

    async def list_mistakes(
        self,
        *,
        current_user: User,
        course_id: UUID | None,
        knowledge_id: UUID | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[MistakeBookRead], int]:
        if course_id is not None:
            await self._get_accessible_course(course_id, current_user)
        items, total = await self.quizzes.list_mistakes(
            user_id=current_user.id,
            course_id=course_id,
            knowledge_id=knowledge_id,
            status=status,
            page=page,
            page_size=page_size,
        )
        return [MistakeBookRead.model_validate(item) for item in items], total

    async def _grade_and_record(
        self,
        *,
        user_id: UUID,
        quiz: Quiz,
        question: Question,
        answer_text: str,
    ) -> tuple[AnswerRecord, MistakeBook | None]:
        is_correct = self._is_correct(question, answer_text)
        error_tags = [] if is_correct else self._ensure_error_tags(question.error_tags)
        now = datetime.now(UTC)
        record = await self.quizzes.create_answer_record(
            record=AnswerRecord(
                user_id=user_id,
                quiz_id=quiz.id,
                question_id=question.id,
                answer_text=answer_text,
                is_correct=is_correct,
                score=Decimal("100.00") if is_correct else Decimal("0.00"),
                feedback=self._feedback(question, is_correct),
                error_tags=error_tags,
                reviewed_at=now,
            )
        )
        if is_correct:
            return record, None

        mistake = await self.quizzes.create_mistake(
            mistake=MistakeBook(
                user_id=user_id,
                course_id=quiz.course_id,
                knowledge_id=question.knowledge_id,
                question_id=question.id,
                answer_record_id=record.id,
                error_summary=f"作答为「{answer_text or '空答案'}」，标准答案为「{question.standard_answer}」。",
                correction=question.analysis or "建议回到对应 Wiki 页面核对概念、操作步骤和边界条件。",
                error_tags=error_tags,
                status="unresolved",
            )
        )
        return record, mistake

    async def _get_accessible_course(self, course_id: UUID, current_user: User) -> Course:
        return await CourseService(self.db).get_readable_course(course_id, current_user)

    async def _get_knowledge(
        self,
        knowledge_id: UUID | None,
        course: Course,
        current_user: User,
    ) -> KnowledgePoint | None:
        if knowledge_id is None:
            return None
        items = await self.knowledge.list_visible_by_course(
            course_id=course.id,
            current_user_id=current_user.id,
            public_owner_id=course.owner_id if course.visibility == "public_template" else None,
            include_all=current_user.role == "admin",
        )
        for item in items:
            if item.id == knowledge_id:
                return item
        raise BusinessException(
            code=ErrorCode.NOT_FOUND,
            detail="知识点不存在",
            status_code=404,
        )

    async def _get_owned_quiz(self, quiz_id: UUID, user_id: UUID) -> Quiz:
        quiz = await self.quizzes.get_quiz_for_user(quiz_id=quiz_id, user_id=user_id)
        if quiz is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="练习不存在",
                status_code=404,
            )
        return quiz

    def _normalize_agent_questions(
        self,
        value: object,
        *,
        topic: str,
        count: int,
        question_types: list[str],
        difficulty: str,
    ) -> list[dict[str, Any]]:
        raw_items = value if isinstance(value, list) else []
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(raw_items[:count]):
            if not isinstance(item, dict):
                continue
            normalized.append(self._normalize_question_item(
                item,
                index=index,
                topic=topic,
                question_type=question_types[index % len(question_types)],
                difficulty=difficulty,
            ))
        while len(normalized) < count:
            index = len(normalized)
            normalized.append(self._fallback_question(
                index=index,
                topic=topic,
                question_type=question_types[index % len(question_types)],
                difficulty=difficulty,
            ))
        return normalized

    def _normalize_question_item(
        self,
        item: dict[str, Any],
        *,
        index: int,
        topic: str,
        question_type: str,
        difficulty: str,
    ) -> dict[str, Any]:
        normalized_type = str(item.get("question_type") or question_type).strip().lower()
        question_text = str(item.get("question_text") or item.get("stem") or "").strip()
        standard_answer = str(item.get("standard_answer") or item.get("correct_answer") or "").strip()
        if not question_text or not standard_answer:
            return self._fallback_question(
                index=index,
                topic=topic,
                question_type=normalized_type or question_type,
                difficulty=difficulty,
            )
        return {
            "question_type": normalized_type or question_type,
            "difficulty": str(item.get("difficulty") or difficulty),
            "question_text": question_text,
            "options": item.get("options") or [],
            "standard_answer": standard_answer,
            "analysis": str(item.get("analysis") or item.get("explanation") or "请结合课程资料复盘该题。"),
            "error_tags": self._ensure_error_tags(item.get("error_tags")),
            "created_by": str(item.get("created_by") or "ai"),
        }

    def _fallback_question(
        self,
        *,
        index: int,
        topic: str,
        question_type: str,
        difficulty: str,
    ) -> dict[str, Any]:
        labels = ["A", "B", "C", "D"]
        return {
            "question_type": question_type,
            "difficulty": difficulty,
            "question_text": f"关于「{topic}」的核心理解，下列说法哪一项最准确？",
            "options": {
                "A": f"{topic}只需要记忆定义，不需要理解操作过程。",
                "B": f"学习{topic}时应同时关注定义、操作过程、复杂度和应用场景。",
                "C": f"{topic}与边界条件无关。",
                "D": f"{topic}只能通过背诵题目掌握。",
            } if question_type in {"single_choice", "multiple_choice"} else [],
            "standard_answer": labels[1] if question_type in {"single_choice", "multiple_choice"} else f"应说明{topic}的定义、操作过程、复杂度和应用场景。",
            "analysis": f"第 {index + 1} 题用于检查对{topic}的整体理解。正确思路是把概念和操作过程联系起来，而不是只背结论。",
            "error_tags": ["概念理解偏差", "过程推演不足"],
            "created_by": "system",
        }

    def _is_correct(self, question: Question, answer_text: str) -> bool:
        answer = self._normalize_answer(answer_text)
        standard = self._normalize_answer(question.standard_answer)
        if question.question_type in {"single_choice", "multiple_choice", "judge"}:
            return answer == standard
        return bool(answer) and (answer == standard or standard in answer or answer in standard)

    def _normalize_answer(self, value: str | None) -> str:
        return "".join(str(value or "").strip().upper().split())

    def _feedback(self, question: Question, is_correct: bool) -> str:
        if is_correct:
            return "回答正确，建议继续用同类题巩固迁移能力。"
        return f"回答错误。标准答案是：{question.standard_answer}。"

    def _ensure_error_tags(self, value: object) -> list[Any]:
        if isinstance(value, list) and value:
            return value
        return ["概念理解偏差"]

    def _topic(
        self,
        topic: str | None,
        knowledge: KnowledgePoint | None,
        course: Course,
    ) -> str:
        cleaned = (topic or "").strip()
        if knowledge is not None:
            return knowledge.name
        if cleaned:
            return cleaned
        return course.title or "数据结构"

    def _uuid(self, value: object) -> UUID | None:
        if isinstance(value, UUID):
            return value
        if isinstance(value, str) and value:
            try:
                return UUID(value)
            except ValueError:
                return None
        return None
