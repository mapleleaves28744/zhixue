from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.provider import get_llm_provider
from app.llm.schemas import ChatMessage
from app.models.quiz import QuizAttempt


class DiagnosisReport:
    def __init__(self, **kwargs: Any):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def model_dump(self, mode: str = "json") -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


class DiagnosisService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze(
        self,
        user_id: UUID,
        course_id: UUID | None = None,
    ) -> DiagnosisReport:
        query = (
            select(QuizAttempt)
            .where(QuizAttempt.user_id == user_id)
        )
        if course_id:
            from app.models.quiz import Quiz
            query = query.join(Quiz, QuizAttempt.quiz_id == Quiz.id).where(Quiz.course_id == course_id)

        query = query.order_by(QuizAttempt.created_at.desc()).limit(50)
        result = await self.db.execute(query)
        attempts = list(result.scalars().all())

        total = len(attempts)
        correct = sum(1 for a in attempts if a.is_correct)
        accuracy = correct / total if total > 0 else 0

        llm = get_llm_provider()

        prompt = f"""你是一个学习诊断专家。请根据以下答题数据分析学生的学习状况。

答题统计：
- 总题数：{total}
- 正确数：{correct}
- 正确率：{accuracy:.1%}

请返回JSON格式的诊断报告：
```json
{{
  "summary": "学习诊断总结",
  "strengths": ["优势1", "优势2"],
  "weaknesses": ["薄弱点1", "薄弱点2"],
  "recommendations": ["建议1", "建议2"],
  "overall_score": 85,
  "focus_areas": ["需要重点学习的领域"]
}}
```"""

        response = await llm.chat(
            messages=[ChatMessage(role="user", content=prompt)],
            max_tokens=2000,
        )
        report_data = self._parse_report(response.content)

        report_data["accuracy"] = accuracy
        report_data["total_questions"] = total
        report_data["correct_answers"] = correct

        return DiagnosisReport(**report_data)

    def _parse_report(self, text: str) -> dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        return {
            "summary": text[:500],
            "strengths": [],
            "weaknesses": [],
            "recommendations": [],
            "overall_score": 0,
            "focus_areas": [],
        }

    async def list_reports(
        self,
        user_id: UUID,
        course_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[DiagnosisReport], int]:
        query = (
            select(QuizAttempt)
            .where(QuizAttempt.user_id == user_id)
        )
        if course_id:
            from app.models.quiz import Quiz
            query = query.join(Quiz, QuizAttempt.quiz_id == Quiz.id).where(Quiz.course_id == course_id)

        total_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = total_result.scalar() or 0

        query = query.order_by(QuizAttempt.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        attempts = list(result.scalars().all())

        reports = []
        for attempt in attempts:
            reports.append(DiagnosisReport(
                id=str(attempt.id),
                quiz_id=str(attempt.quiz_id),
                user_answer=attempt.user_answer,
                is_correct=attempt.is_correct,
                created_at=attempt.created_at.isoformat() if attempt.created_at else None,
            ))

        return reports, total
