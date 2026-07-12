from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.tools import ToolContext, ToolExecutionResult, ToolRegistry
from app.agent_runtime.toolsets.common import register_tool
from app.models.user import User


def register_profile_tools(
    registry: ToolRegistry,
    db: AsyncSession,
    current_user: User,
    *,
    tool_names: Iterable[str] | None = None,
) -> None:
    selected = set(tool_names or ())

    def include(name: str) -> bool:
        return not selected or name in selected

    async def rebuild_profile(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.services.profile_service import ProfileService

        result = await ProfileService(db).rebuild(current_user.id)
        data = result.model_dump(mode="json")
        return ToolExecutionResult(
            output=data,
            evidence=["基于当前用户学习记录重建"],
            artifact_refs=[{"type": "profile_update", "id": str(result.id)}],
        )

    async def update_profile_from_dialogue(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.services.profile_service import ProfileService

        result = await ProfileService(db).ingest_dialogue_profile(
            user_id=current_user.id,
            course_id=context.course_id,
            dialogue_text=str(arguments["dialogue_text"]),
            source_message_id=str(arguments.get("source_message_id") or context.tool_call_id),
        )
        data = result.model_dump(mode="json")
        artifact_refs = [{"type": "profile_update", "id": str(result.profile.id)}]
        if result.preferences is not None:
            artifact_refs.append({"type": "learning_preference", "id": str(result.preferences.id)})
        return ToolExecutionResult(output=data, evidence=[data.get("evidence") or {}], artifact_refs=artifact_refs)

    async def reflect_memory(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.services.memory_service import MemoryService

        results = await MemoryService(db).reflect(current_user.id, context.course_id)
        data = [item.model_dump(mode="json") for item in results]
        return ToolExecutionResult(
            output={"items": data},
            evidence=[{"memory_id": str(item.id), "evidence": item.evidence} for item in results],
            artifact_refs=[{"type": "memory_reflection", "count": len(results)}],
        )

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

    if include("update_profile_from_dialogue"):
        register_tool(registry, "update_profile_from_dialogue", "从学生自然语言对话中提取学习目标、专业年级、偏好、薄弱点和错误模式，并带证据更新画像。", "ProfileAgent", {"dialogue_text": {"type": "string"}, "source_message_id": {"type": "string"}}, ["dialogue_text"], update_profile_from_dialogue, writes_db=True)
    if include("rebuild_profile"):
        register_tool(registry, "rebuild_profile", "基于学习证据重建学生画像。", "ProfileAgent", {}, [], rebuild_profile, writes_db=True)
    if include("reflect_learning_memory"):
        register_tool(registry, "reflect_learning_memory", "提炼带证据的长期学习记忆。", "MemoryAgent", {}, [], reflect_memory, writes_db=True)
    if include("apply_evolution_strategy"):
        register_tool(registry, "apply_evolution_strategy", "应用已生成的自进化策略。该操作必须获得用户确认。", "EvolutionAgent", {"strategy_id": {"type": "string"}}, [], apply_evolution, writes_db=True, risk_level="high", requires_confirmation=True)
