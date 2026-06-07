from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.tools import AgentTool, ToolContext, ToolExecutionResult, ToolRegistry
from app.models.user import User


def build_learning_tool_registry(
    db: AsyncSession,
    current_user: User,
    *,
    result_loader=None,
    result_saver=None,
) -> ToolRegistry:
    registry = ToolRegistry(result_loader=result_loader, result_saver=result_saver)

    async def search_knowledge(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.services.knowledge_search_service import KnowledgeSearchService

        items = await KnowledgeSearchService(db).search(
            current_user=current_user,
            course_id=context.course_id,
            query=str(arguments["query"]),
            top_k=int(arguments.get("top_k") or 5),
        )
        citations = [
            {
                "source_type": "document",
                "title": item.get("source_title") or "课程资料",
                "source_id": item.get("material_id"),
                "chunk_id": item.get("chunk_id"),
                "page_no": item.get("page_no"),
                "score": item.get("score"),
                "quote": str(item.get("content") or "")[:300],
            }
            for item in items
        ]
        return ToolExecutionResult(output={"items": items}, evidence=citations, citations=citations)

    async def answer_question(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.schemas.tutor import TutorChatRequest
        from app.services.tutor_service import TutorService

        result = await TutorService(db).chat(
            payload=TutorChatRequest(
                course_id=context.course_id,
                question=str(arguments["question"]),
                top_k=int(arguments.get("top_k") or 5),
            ),
            current_user=current_user,
        )
        data = result.model_dump(mode="json")
        refs = [{"type": "tutor_answer", "id": str(result.message_id)}] if result.message_id else []
        return ToolExecutionResult(
            output=data,
            evidence=data.get("citations") or [],
            citations=data.get("citations") or [],
            artifact_refs=refs,
        )

    async def generate_path(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.schemas.learning_path import LearningPathGenerateRequest
        from app.services.learning_path_service import LearningPathService

        result = await LearningPathService(db).generate(
            payload=LearningPathGenerateRequest(
                course_id=context.course_id,
                goal=str(arguments["goal"]),
            ),
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
            artifact_refs=[{"type": "resource", "id": str(result.resource_id), "title": result.title}],
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

    async def rebuild_profile(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.services.profile_service import ProfileService

        result = await ProfileService(db).rebuild(current_user.id)
        data = result.model_dump(mode="json")
        return ToolExecutionResult(
            output=data,
            evidence=["基于当前用户学习记录重建"],
            artifact_refs=[{"type": "profile_update", "id": str(result.id)}],
        )

    async def reflect_memory(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.services.memory_service import MemoryService

        results = await MemoryService(db).reflect(current_user.id, context.course_id)
        data = [item.model_dump(mode="json") for item in results]
        return ToolExecutionResult(
            output={"items": data},
            evidence=[{"memory_id": str(item.id), "evidence": item.evidence} for item in results],
            artifact_refs=[{"type": "memory_reflection", "count": len(results)}],
        )

    async def review_artifacts(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.services.agent_service import AgentService

        result = await AgentService(db).run_task(
            task_type="review_content",
            user_id=current_user.id,
            course_id=context.course_id,
            params={"content": str(arguments.get("content") or "")[:4000]},
        )
        if not result.success:
            raise RuntimeError(result.message)
        return ToolExecutionResult(output=result.data, evidence=result.evidence)

    async def apply_evolution(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.services.evolution_service import EvolutionService

        service = EvolutionService(db)
        strategy_id = arguments.get("strategy_id")
        if not strategy_id:
            items, _ = await service.list_strategies(
                user_id=current_user.id,
                course_id=context.course_id,
                status="draft",
                page_size=1,
            )
            if not items:
                raise RuntimeError("当前没有可应用的草稿自进化策略")
            strategy_id = items[0].id
        result = await service.apply_strategy(UUID(str(strategy_id)), current_user.id)
        return ToolExecutionResult(
            output=result.model_dump(mode="json"),
            artifact_refs=[{"type": "evolution_strategy", "id": str(result.id), "status": result.status}],
        )

    _register(
        registry,
        name="search_course_knowledge",
        description="使用向量、关键词、metadata 和 rerank 混合检索课程资料，返回可引用片段。",
        agent_name="KnowledgeAgent",
        properties={"query": {"type": "string"}, "top_k": {"type": "integer", "minimum": 1, "maximum": 20}},
        required=["query"],
        handler=search_knowledge,
    )
    _register(
        registry,
        name="answer_course_question",
        description="基于课程知识库、Wiki 和学生画像回答学习问题。",
        agent_name="TutorAgent",
        properties={"question": {"type": "string"}, "top_k": {"type": "integer", "minimum": 1, "maximum": 20}},
        required=["question"],
        handler=answer_question,
        writes_db=True,
    )
    _register(
        registry,
        name="generate_learning_path",
        description="根据学习目标、薄弱点和课程知识点生成个性化学习路径。",
        agent_name="PlannerAgent",
        properties={"goal": {"type": "string"}},
        required=["goal"],
        handler=generate_path,
        writes_db=True,
    )
    _register(
        registry,
        name="generate_explanation",
        description="围绕知识主题生成带来源和个性化理由的学习资源。",
        agent_name="ResourceAgent",
        properties={
            "topic": {"type": "string"},
            "resource_type": {"type": "string", "enum": ["explanation", "summary", "example", "flashcard", "review"]},
            "requirement": {"type": "string"},
        },
        required=["topic"],
        handler=generate_explanation,
        writes_db=True,
    )
    _register(
        registry,
        name="generate_quiz",
        description="围绕主题生成结构化练习题。",
        agent_name="QuizAgent",
        properties={
            "topic": {"type": "string"},
            "count": {"type": "integer", "minimum": 1, "maximum": 20},
            "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
            "question_types": {"type": "array", "items": {"type": "string"}},
        },
        required=["topic"],
        handler=generate_quiz,
        writes_db=True,
    )
    _register(registry, "analyze_learning_diagnosis", "基于练习和错题生成学习诊断。", "DiagnosisAgent", {}, [], analyze_diagnosis, writes_db=True)
    _register(registry, "refresh_recommendations", "根据画像、诊断和路径刷新推荐。", "RecommendAgent", {}, [], refresh_recommendations, writes_db=True)
    _register(registry, "rebuild_profile", "基于学习证据重建学生画像。", "ProfileAgent", {}, [], rebuild_profile, writes_db=True)
    _register(registry, "reflect_learning_memory", "提炼带证据的长期学习记忆。", "MemoryAgent", {}, [], reflect_memory, writes_db=True)
    _register(
        registry,
        "review_artifacts",
        "审查生成内容的来源、幻觉和风险。",
        "ReviewAgent",
        {"content": {"type": "string"}},
        ["content"],
        review_artifacts,
    )
    _register(
        registry,
        "apply_evolution_strategy",
        "应用已生成的自进化策略。该操作必须获得用户确认。",
        "EvolutionAgent",
        {"strategy_id": {"type": "string"}},
        [],
        apply_evolution,
        writes_db=True,
        risk_level="high",
        requires_confirmation=True,
    )
    return registry


def _register(
    registry: ToolRegistry,
    name: str,
    description: str,
    agent_name: str,
    properties: dict[str, Any],
    required: list[str],
    handler,
    *,
    writes_db: bool = False,
    risk_level: str = "low",
    requires_confirmation: bool = False,
) -> None:
    registry.register(
        AgentTool(
            name=name,
            description=description,
            agent_name=agent_name,
            input_schema={
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
            handler=handler,
            writes_db=writes_db,
            risk_level=risk_level,  # type: ignore[arg-type]
            requires_confirmation=requires_confirmation,
        )
    )
