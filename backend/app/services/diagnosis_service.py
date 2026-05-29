from __future__ import annotations

from collections import Counter
from typing import Any
from uuid import UUID

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context import AgentContext
from app.agents.orchestrator import OrchestratorAgent
from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.diagnosis import DiagnosisReport
from app.models.knowledge import KnowledgePoint
from app.models.quiz import AnswerRecord, MistakeBook, Question, Quiz
from app.models.user import User
from app.services.course_service import CourseService


class DiagnosisService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze(
        self,
        *,
        current_user: User,
        course_id: UUID,
        trigger_evolution: bool = False,
    ) -> dict[str, Any]:
        course = await CourseService(self.db).get_readable_course(course_id, current_user)

        answer_records = await self._list_recent_answers(current_user.id, course_id)
        mistake_records = await self._list_mistakes(current_user.id, course_id)
        mastery = await self.get_mastery(user_id=current_user.id, course_id=course_id)
        mastery["summary_stats"] = self._answer_stats(answer_records)
        weak_points = self._build_weak_points(mastery["items"], mistake_records)
        error_patterns = self._build_error_patterns(answer_records, mistake_records)
        recommended_actions = self._build_recommended_actions(
            weak_points,
            error_patterns,
            course_title=course.title,
        )
        summary = self._default_summary(answer_records, weak_points)

        agent_run_id: UUID | None = None
        agent_summary = await self._generate_agent_summary(
            user_id=current_user.id,
            course_id=course_id,
            summary=summary,
            mastery=mastery,
            weak_points=weak_points,
            error_patterns=error_patterns,
            recommended_actions=recommended_actions,
            trigger_evolution=trigger_evolution,
        )
        if agent_summary:
            summary = agent_summary.get("summary") or summary
            agent_run_id = agent_summary.get("agent_run_id")

        report = DiagnosisReport(
            user_id=current_user.id,
            course_id=course_id,
            report_type="practice",
            summary=summary,
            mastery_result=mastery,
            weak_points=weak_points,
            error_patterns=error_patterns,
            recommended_actions=recommended_actions,
            generated_by_agent_run_id=agent_run_id,
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return self._serialize_report(report)

    async def list_reports(
        self,
        user_id: UUID,
        course_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = select(DiagnosisReport).where(DiagnosisReport.user_id == user_id)
        if course_id is not None:
            stmt = stmt.where(DiagnosisReport.course_id == course_id)

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(total_stmt)).scalar() or 0
        stmt = stmt.order_by(DiagnosisReport.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        reports = result.scalars().all()
        return [self._serialize_report(report) for report in reports], total

    async def get_report(self, report_id: UUID, user_id: UUID) -> dict[str, Any]:
        report = await self.db.get(DiagnosisReport, report_id)
        if report is None or report.user_id != user_id:
            raise BusinessException(code=ErrorCode.NOT_FOUND, detail="诊断报告不存在", status_code=404)
        return self._serialize_report(report)

    async def get_mastery(
        self,
        user_id: UUID,
        course_id: UUID | None = None,
    ) -> dict[str, Any]:
        stmt = (
            select(
                Question.knowledge_id,
                KnowledgePoint.name,
                func.count(AnswerRecord.id).label("total"),
                func.sum(func.cast(AnswerRecord.is_correct, Integer)).label("correct"),
            )
            .join(Question, AnswerRecord.question_id == Question.id)
            .outerjoin(KnowledgePoint, Question.knowledge_id == KnowledgePoint.id)
            .where(AnswerRecord.user_id == user_id)
            .where(Question.knowledge_id.isnot(None))
        )
        if course_id is not None:
            stmt = stmt.join(Quiz, AnswerRecord.quiz_id == Quiz.id).where(Quiz.course_id == course_id)

        stmt = stmt.group_by(Question.knowledge_id, KnowledgePoint.name)
        result = await self.db.execute(stmt)
        items: list[dict[str, Any]] = []
        for knowledge_id, knowledge_name, total, correct in result.all():
            correct_count = correct or 0
            mastery_level = correct_count / total if total > 0 else 0
            items.append(
                {
                    "knowledge_id": str(knowledge_id),
                    "knowledge_name": knowledge_name or "未命名知识点",
                    "total_attempts": total,
                    "correct_count": correct_count,
                    "mastery_level": round(mastery_level, 2),
                }
            )

        return {"items": items, "course_id": str(course_id) if course_id else None}

    async def _list_recent_answers(self, user_id: UUID, course_id: UUID) -> list[AnswerRecord]:
        stmt = (
            select(AnswerRecord)
            .join(Quiz, AnswerRecord.quiz_id == Quiz.id)
            .where(AnswerRecord.user_id == user_id, Quiz.course_id == course_id)
            .order_by(AnswerRecord.answered_at.desc())
            .limit(50)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _list_mistakes(self, user_id: UUID, course_id: UUID) -> list[MistakeBook]:
        stmt = (
            select(MistakeBook)
            .where(MistakeBook.user_id == user_id, MistakeBook.course_id == course_id)
            .order_by(MistakeBook.created_at.desc())
            .limit(50)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _generate_agent_summary(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        summary: str,
        mastery: dict[str, Any],
        weak_points: list[dict[str, Any]],
        error_patterns: list[dict[str, Any]],
        recommended_actions: list[dict[str, Any]],
        trigger_evolution: bool,
    ) -> dict[str, Any] | None:
        context_text = "\n".join(
            [
                f"规则摘要：{summary}",
                f"掌握度：{mastery}",
                f"薄弱点：{weak_points}",
                f"错因模式：{error_patterns}",
                f"建议动作：{recommended_actions}",
                f"是否触发自进化：{trigger_evolution}",
            ]
        )
        context = AgentContext(
            user_id=user_id,
            course_id=course_id,
            task_type="diagnose_student",
            params={"diagnosis_context": context_text},
        )
        result = await OrchestratorAgent(self.db).run(context)
        if not result.success:
            return None
        return {
            "summary": str(result.data.get("diagnosis_result") or "").strip() or None,
            "agent_run_id": context.run_id,
        }

    def _build_weak_points(
        self,
        mastery_items: list[dict[str, Any]],
        mistakes: list[MistakeBook],
    ) -> list[dict[str, Any]]:
        mistake_counts: Counter[str] = Counter(str(item.knowledge_id) for item in mistakes if item.knowledge_id)
        items: list[dict[str, Any]] = []
        for item in mastery_items:
            mastery_level = float(item.get("mastery_level") or 0)
            mistake_count = mistake_counts.get(str(item.get("knowledge_id")), 0)
            if mastery_level < 0.8 or mistake_count:
                severity = "high" if mastery_level < 0.5 or mistake_count >= 3 else "medium"
                items.append(
                    {
                        "knowledge_id": item.get("knowledge_id"),
                        "knowledge_name": item.get("knowledge_name"),
                        "mastery_level": mastery_level,
                        "mistake_count": mistake_count,
                        "severity": severity,
                    }
                )
        return sorted(items, key=lambda x: (x["severity"] != "high", x["mastery_level"], -x["mistake_count"]))[:8]

    def _build_error_patterns(
        self,
        answers: list[AnswerRecord],
        mistakes: list[MistakeBook],
    ) -> list[dict[str, Any]]:
        counter: Counter[str] = Counter()
        for answer in answers:
            for tag in answer.error_tags or []:
                counter[str(tag)] += 1
        for mistake in mistakes:
            for tag in mistake.error_tags or []:
                counter[str(tag)] += 1
        if not counter and any(answer.is_correct is False for answer in answers):
            counter["答案匹配错误或概念掌握不稳"] = sum(1 for answer in answers if answer.is_correct is False)
        return [
            {"pattern": pattern, "count": count, "evidence": "answer_records_and_mistake_books"}
            for pattern, count in counter.most_common(6)
        ]

    def _build_recommended_actions(
        self,
        weak_points: list[dict[str, Any]],
        error_patterns: list[dict[str, Any]],
        course_title: str | None = None,
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        for index, point in enumerate(weak_points[:5], start=1):
            actions.append(
                {
                    "action_type": "review_and_practice",
                    "title": f"复习并练习：{point.get('knowledge_name') or '薄弱知识点'}",
                    "reason": f"掌握度 {point.get('mastery_level', 0):.0%}，错题数 {point.get('mistake_count', 0)}。",
                    "priority": index,
                    "target_id": point.get("knowledge_id"),
                }
            )
        for pattern in error_patterns[:2]:
            actions.append(
                {
                    "action_type": "mistake_pattern",
                    "title": f"整理错因：{pattern['pattern']}",
                    "reason": f"近期出现 {pattern['count']} 次，需要形成纠错笔记。",
                    "priority": len(actions) + 1,
                    "target_id": None,
                }
            )
        if not actions:
            normalized_title = (course_title or "").strip()
            practice_title = (
                f"继续完成一组《{normalized_title}》练习"
                if normalized_title
                else "继续完成一组当前课程练习"
            )
            actions.append(
                {
                    "action_type": "continue_learning",
                    "title": practice_title,
                    "reason": "当前诊断证据较少，需要更多答题记录来稳定判断薄弱点。",
                    "priority": 1,
                    "target_id": None,
                }
            )
        return actions

    def _default_summary(self, answers: list[AnswerRecord], weak_points: list[dict[str, Any]]) -> str:
        total = len(answers)
        correct = sum(1 for answer in answers if answer.is_correct)
        accuracy = correct / total if total else 0
        if not total:
            return "当前课程还没有足够答题记录，建议先完成一组练习后再生成诊断。"
        if weak_points:
            names = "、".join(str(item.get("knowledge_name")) for item in weak_points[:3])
            return f"最近 {total} 次答题正确率为 {accuracy:.0%}，需要优先补强 {names}。"
        return f"最近 {total} 次答题正确率为 {accuracy:.0%}，整体表现稳定，可继续推进下一阶段学习。"

    def _answer_stats(self, answers: list[AnswerRecord]) -> dict[str, Any]:
        total = len(answers)
        correct = sum(1 for answer in answers if answer.is_correct)
        accuracy = correct / total if total else 0
        return {
            "total_questions": total,
            "correct_answers": correct,
            "accuracy": round(accuracy, 4),
        }

    def _serialize_report(self, report: DiagnosisReport) -> dict[str, Any]:
        stats = (report.mastery_result or {}).get("summary_stats") or {}
        weaknesses = [
            f"{item.get('knowledge_name')}（掌握度 {float(item.get('mastery_level') or 0):.0%}）"
            for item in (report.weak_points or [])
        ]
        accuracy = float(stats.get("accuracy") or 0)
        return {
            "id": str(report.id),
            "user_id": str(report.user_id),
            "course_id": str(report.course_id),
            "report_type": report.report_type,
            "summary": report.summary,
            "accuracy": accuracy,
            "total_questions": int(stats.get("total_questions") or 0),
            "correct_answers": int(stats.get("correct_answers") or 0),
            "strengths": ["当前没有明显高风险薄弱点"] if not weaknesses else [],
            "weaknesses": weaknesses,
            "mastery_result": report.mastery_result or {},
            "weak_points": report.weak_points or [],
            "error_patterns": report.error_patterns or [],
            "recommended_actions": report.recommended_actions or [],
            "recommendations": [
                item.get("title") for item in (report.recommended_actions or []) if item.get("title")
            ],
            "generated_by_agent_run_id": str(report.generated_by_agent_run_id) if report.generated_by_agent_run_id else None,
            "created_at": report.created_at.isoformat() if report.created_at else None,
        }
