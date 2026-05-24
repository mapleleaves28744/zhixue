from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BusinessException
from app.llm.provider import get_llm_provider
from app.llm.schemas import ChatMessage
from app.models.quiz import Quiz, QuizAttempt


class QuizService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_quizzes(
        self,
        user_id: UUID,
        course_id: UUID,
        topic: str,
        count: int = 5,
        difficulty: str = "medium",
    ) -> list[Quiz]:
        llm = get_llm_provider()

        prompt = f"""你是一个教育出题专家。请根据以下要求生成{count}道练习题。

主题：{topic}
难度：{difficulty}
课程ID：{course_id}

请严格按照以下JSON格式返回，不要包含其他内容：
```json
[
  {{
    "title": "题目标题",
    "question_text": "题目内容",
    "question_type": "multiple_choice",
    "options": {{"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"}},
    "correct_answer": "A",
    "explanation": "解析说明",
    "knowledge_tags": ["知识点1", "知识点2"]
  }}
]
```

要求：
1. 题目必须准确、有教育价值
2. 选项必须有干扰性但只有一个正确答案
3. explanation 必须详细解释为什么选择该答案
4. knowledge_tags 标注涉及的知识点"""

        response = await llm.chat(
            messages=[ChatMessage(role="user", content=prompt)],
            max_tokens=4000,
        )
        quizzes = self._parse_quizzes(response.content)

        created_quizzes = []
        for q in quizzes:
            quiz = Quiz(
                course_id=course_id,
                created_by=user_id,
                title=q.get("title", "练习题"),
                question_type=q.get("question_type", "multiple_choice"),
                difficulty=difficulty,
                question_text=q.get("question_text", ""),
                options=q.get("options"),
                correct_answer=q.get("correct_answer", ""),
                explanation=q.get("explanation"),
                knowledge_tags=q.get("knowledge_tags"),
            )
            self.db.add(quiz)
            created_quizzes.append(quiz)

        await self.db.commit()
        for q in created_quizzes:
            await self.db.refresh(q)
        return created_quizzes

    def _parse_quizzes(self, text: str) -> list[dict[str, Any]]:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "quizzes" in data:
                return data["quizzes"]
        except json.JSONDecodeError:
            pass

        return [{
            "title": "练习题",
            "question_text": text[:500],
            "question_type": "multiple_choice",
            "options": {"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"},
            "correct_answer": "A",
            "explanation": "AI 生成的练习题",
            "knowledge_tags": [],
        }]

    async def list_quizzes(
        self,
        user_id: UUID,
        course_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Quiz], int]:
        query = select(Quiz).where(Quiz.status == "active")
        count_query = select(func.count(Quiz.id)).where(Quiz.status == "active")

        if course_id:
            query = query.where(Quiz.course_id == course_id)
            count_query = count_query.where(Quiz.course_id == course_id)

        total = (await self.db.execute(count_query)).scalar() or 0
        query = query.order_by(Quiz.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def submit_answer(
        self,
        user_id: UUID,
        quiz_id: UUID,
        user_answer: str,
        time_spent_seconds: int | None = None,
    ) -> QuizAttempt:
        result = await self.db.execute(select(Quiz).where(Quiz.id == quiz_id))
        quiz = result.scalar_one_or_none()
        if not quiz:
            raise BusinessException(code=40401, message="题目不存在")

        is_correct = user_answer.strip().upper() == quiz.correct_answer.strip().upper()

        attempt = QuizAttempt(
            user_id=user_id,
            quiz_id=quiz_id,
            user_answer=user_answer,
            is_correct=is_correct,
            time_spent_seconds=time_spent_seconds,
        )
        self.db.add(attempt)
        await self.db.commit()
        await self.db.refresh(attempt)
        return attempt

    async def get_wrong_questions(
        self,
        user_id: UUID,
        course_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[QuizAttempt], int]:
        query = (
            select(QuizAttempt)
            .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
            .where(QuizAttempt.user_id == user_id, QuizAttempt.is_correct == False)
        )
        count_query = (
            select(func.count(QuizAttempt.id))
            .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
            .where(QuizAttempt.user_id == user_id, QuizAttempt.is_correct == False)
        )

        if course_id:
            query = query.where(Quiz.course_id == course_id)
            count_query = count_query.where(Quiz.course_id == course_id)

        total = (await self.db.execute(count_query)).scalar() or 0
        query = query.options(selectinload(QuizAttempt.quiz))
        query = query.order_by(QuizAttempt.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_attempts(
        self,
        user_id: UUID,
        quiz_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[QuizAttempt], int]:
        query = select(QuizAttempt).where(QuizAttempt.user_id == user_id)
        count_query = select(func.count(QuizAttempt.id)).where(QuizAttempt.user_id == user_id)

        if quiz_id:
            query = query.where(QuizAttempt.quiz_id == quiz_id)
            count_query = count_query.where(QuizAttempt.quiz_id == quiz_id)

        total = (await self.db.execute(count_query)).scalar() or 0
        query = query.options(selectinload(QuizAttempt.quiz))
        query = query.order_by(QuizAttempt.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total
