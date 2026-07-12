from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.tools import ToolContext, ToolExecutionResult, ToolRegistry
from app.agent_runtime.toolsets.common import register_tool
from app.models.user import User


def register_learning_tools(
    registry: ToolRegistry,
    db: AsyncSession,
    current_user: User,
    *,
    tool_names: Iterable[str] | None = None,
) -> None:
    selected = set(tool_names or ())

    def include(name: str) -> bool:
        return not selected or name in selected

    async def answer_question(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.schemas.tutor import TutorChatRequest
        from app.services.grounded_qa_pipeline import GroundedQaPipeline

        result = await GroundedQaPipeline(db).answer(
            TutorChatRequest(
                course_id=context.course_id,
                conversation_id=context.conversation_id,
                question=str(arguments["question"]),
                top_k=int(arguments.get("top_k") or 5),
            ),
            current_user,
            persist_conversation_messages=False,
        )
        data = result.model_dump(mode="json")
        refs = [{"type": "tutor_answer", "id": str(result.message_id)}] if result.message_id else []
        return ToolExecutionResult(
            output=data,
            evidence=data.get("citations") or [],
            citations=data.get("citations") or [],
            artifact_refs=refs,
            final_answer=result.answer,
        )

    async def generate_path(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.schemas.learning_path import LearningPathGenerateRequest
        from app.services.learning_path_service import LearningPathService

        result = await LearningPathService(db).generate(
            payload=LearningPathGenerateRequest(course_id=context.course_id, goal=str(arguments["goal"])),
            current_user=current_user,
        )
        data = result.model_dump(mode="json")
        return ToolExecutionResult(
            output=data,
            evidence=[result.reason or "基于课程知识点、画像和目标生成"],
            artifact_refs=[{"type": "learning_path", "id": str(result.id), "title": result.title}],
        )

    async def generate_explanation(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.schemas.resource import ResourceGenerateRequest
        from app.services.resource_service import ResourceService

        topic = str(arguments["topic"])
        result = await ResourceService(db).generate_resource(
            payload=ResourceGenerateRequest(
                course_id=context.course_id,
                resource_type=str(arguments.get("resource_type") or "explanation"),
                requirement=str(arguments.get("requirement") or f"围绕{topic}生成分步骤讲解并引用课程资料。"),
                use_profile=True,
            ),
            current_user=current_user,
        )
        data = result.model_dump(mode="json")
        return ToolExecutionResult(
            output=data,
            evidence=data.get("citations") or [],
            citations=data.get("citations") or [],
            artifact_refs=[
                {
                    "type": "resource",
                    "subtype": data.get("resource_type"),
                    "resource_type": data.get("resource_type"),
                    "id": str(result.resource_id),
                    "resource_id": str(result.resource_id),
                    "title": result.title,
                }
            ],
        )

    async def generate_quiz(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.schemas.quiz import QuizGenerateRequest
        from app.services.quiz_service import QuizService

        result = await QuizService(db).generate_quiz(
            payload=QuizGenerateRequest(
                course_id=context.course_id,
                topic=str(arguments["topic"]),
                count=int(arguments.get("count") or 5),
                difficulty=str(arguments.get("difficulty") or "medium"),
                question_types=list(arguments.get("question_types") or ["single_choice"]),
            ),
            current_user=current_user,
        )
        data = result.model_dump(mode="json")
        return ToolExecutionResult(
            output=data,
            evidence=[f"生成 {len(result.questions)} 道结构化练习"],
            artifact_refs=[{"type": "quiz", "id": str(result.quiz_id), "title": result.title}],
        )

    async def analyze_diagnosis(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.services.diagnosis_service import DiagnosisService

        result = await DiagnosisService(db).analyze(
            current_user=current_user,
            course_id=context.course_id,
            trigger_evolution=False,
        )
        return ToolExecutionResult(
            output=result,
            evidence=result.get("weak_points") or [],
            artifact_refs=[{"type": "diagnosis_report", "id": str(result.get("id") or "")}],
        )

    async def refresh_recommendations(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.services.recommendation_service import RecommendationService

        result = await RecommendationService(db).refresh_recommendations(
            current_user=current_user,
            course_id=context.course_id,
        )
        return ToolExecutionResult(
            output=result,
            evidence=["基于画像、诊断与学习路径刷新"],
            artifact_refs=[{"type": "recommendations", "count": result["refreshed_count"]}],
        )

    if include("answer_course_question"):
        register_tool(registry, "answer_course_question", "基于课程知识库、Wiki 和学生画像回答学习问题。", "TutorAgent", {"question": {"type": "string"}, "top_k": {"type": "integer", "minimum": 1, "maximum": 20}}, ["question"], answer_question, writes_db=True)
    if include("generate_learning_path"):
        register_tool(registry, "generate_learning_path", "根据学习目标、薄弱点和课程知识点生成个性化学习路径。", "PlannerAgent", {"goal": {"type": "string"}}, ["goal"], generate_path, writes_db=True)
    if include("generate_explanation"):
        register_tool(registry, "generate_explanation", "围绕知识主题生成带来源和个性化理由的学习资源。", "ResourceAgent", {"topic": {"type": "string"}, "resource_type": {"type": "string", "enum": ["explanation", "summary", "example", "flashcard", "review"]}, "requirement": {"type": "string"}}, ["topic"], generate_explanation, writes_db=True)
    if include("generate_quiz"):
        register_tool(registry, "generate_quiz", "围绕主题生成结构化练习题。", "QuizAgent", {"topic": {"type": "string"}, "count": {"type": "integer", "minimum": 1, "maximum": 20}, "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]}, "question_types": {"type": "array", "items": {"type": "string"}}}, ["topic"], generate_quiz, writes_db=True)
    if include("analyze_learning_diagnosis"):
        register_tool(registry, "analyze_learning_diagnosis", "基于练习和错题生成学习诊断。", "DiagnosisAgent", {}, [], analyze_diagnosis, writes_db=True)
    if include("refresh_recommendations"):
        register_tool(registry, "refresh_recommendations", "根据画像、诊断和路径刷新推荐。", "RecommendAgent", {}, [], refresh_recommendations, writes_db=True)
