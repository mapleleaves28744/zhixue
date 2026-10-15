"""Real PostgreSQL/Qwen checks for new material and quiz reference boundaries."""
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.course import Course
from app.models.material import CourseMaterial
from app.models.chunk import DocumentChunk
from app.repositories.quiz_repository import QuizRepository
from app.services.tutor_service import TutorService
from app.services.conversation_context_service import ConversationContext
from app.schemas.tutor import TutorChatRequest
from app.llm.adapters.openai_compatible import OpenAICompatibleLLMProvider
from evaluation_budget import BudgetProvider, EvaluationLedger
from evaluate_context_quality import BASE


async def main():
    output = BASE / "boundary-report.json"
    if output.exists():
        print(output.read_text(encoding="utf-8"))
        return
    ledger = EvaluationLedger(BASE / "budget.sqlite")
    provider = BudgetProvider(OpenAICompatibleLLMProvider(api_key=settings.llm_api_key, base_url=settings.llm_base_url,
        model=settings.llm_model_name, timeout=90), ledger)
    report = {"started_at": datetime.now(UTC).isoformat(), "scope": "synthetic PostgreSQL fixtures, real Tutor Service and real Qwen", "checks": []}
    owner = UUID(json.loads((BASE / "memory-fixtures.json").read_text(encoding="utf-8"))["owner_id"])
    async with AsyncSessionLocal() as db:
        user = await db.get(User, owner)
        course = Course(owner_id=owner, title="合成资料题号边界", visibility="private", status="active")
        db.add(course)
        await db.flush()
        materials = [CourseMaterial(course_id=course.id, uploaded_by=owner, file_name=name, file_type="txt",
                    storage_path="synthetic-evaluation-only", parse_status="parsed") for name in ("参考资料.txt", "完整讲义.txt")]
        db.add_all(materials)
        await db.flush()
        for index in range(30):
            content = "线性结构包含栈与队列。栈遵循后进先出，队列遵循先进先出。" * 12
            if index == 0:
                content = "首段测试标记 HEAD-729。" + content
            if index == 29:
                content += "全文末尾测试标记 TAIL-853。"
            db.add(DocumentChunk(material_id=materials[1].id, course_id=course.id, chunk_index=index,
                                  content=content, page_no=index + 1))
        quiz_repo = QuizRepository(db)
        quiz = await quiz_repo.create_quiz(user_id=owner, course_id=course.id, knowledge_id=None,
            title="题号核验", quiz_type="practice", difficulty="easy")
        questions = await quiz_repo.create_questions(quiz=quiz, items=[
            {"question_type": "single_choice", "question_text": "栈遵循哪种顺序？", "options": {"A": "先进先出", "B": "后进先出"}, "standard_answer": "B", "analysis": "栈遵循后进先出"},
            {"question_type": "single_choice", "question_text": "队列遵循哪种顺序？", "options": {"A": "后进先出", "B": "先进先出"}, "standard_answer": "B", "analysis": "队列遵循先进先出"},
        ])
        await db.commit()
        service = TutorService(db)
        context = ConversationContext(material_references=tuple({"id": str(item.id), "title": item.file_name} for item in materials))
        provider.case_id = "boundary:full-material"
        with patch("app.llm.provider.get_llm_provider", return_value=provider):
            answer, citations, source = await service._answer_material_reference(context=context,
                payload=TutorChatRequest(course_id=course.id, question="总结第二份资料全文，保留首段和末尾的两个测试标记"), current_user=user, course=course)
        report["checks"].append({"name": "full_material_ordinal_and_tail_coverage", "passed": "HEAD-729" in answer and "TAIL-853" in answer
                and len(citations) == 30 and all(item["source_id"] == str(materials[1].id) for item in citations),
                "answer": answer, "citation_count": len(citations), "provider": source})
        provider.case_id = "boundary:quiz-ordinal"
        with patch("app.llm.provider.get_llm_provider", return_value=provider):
            answer, citations, source = await service._answer_quiz_option(context=ConversationContext(quiz_reference={"id": str(quiz.id)}),
                payload=TutorChatRequest(course_id=course.id, question="讲解第二题选项B"), current_user=user, course=course)
        report["checks"].append({"name": "persisted_second_question_option", "passed": bool(citations) and citations[0]["source_id"] == str(questions[1].id)
                and "先进先出" in answer, "answer": answer, "provider": source})
        foreign = Course(owner_id=owner, title="不同课程边界", visibility="private", status="active")
        db.add(foreign)
        await db.commit()
        answer, citations, source = await service._answer_material_reference(context=context,
            payload=TutorChatRequest(course_id=foreign.id, question="总结第二份资料"), current_user=user, course=foreign)
        report["checks"].append({"name": "foreign_course_material_rejected", "passed": not citations and source == "rule", "answer": answer})
    report["passed"] = all(item["passed"] for item in report["checks"])
    report["usage"] = [response.usage for response in provider.responses]
    report["budget"] = ledger.snapshot()
    report["finished_at"] = datetime.now(UTC).isoformat()
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print({"passed": report["passed"], "checks": [(item["name"], item["passed"]) for item in report["checks"]]}, flush=True)
    if not report["passed"]:
        raise SystemExit(1)

if __name__ == "__main__":
    if sys.platform == "win32": asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
