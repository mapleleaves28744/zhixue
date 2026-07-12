from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.tools import ToolContext, ToolExecutionResult, ToolRegistry
from app.agent_runtime.toolsets.common import register_tool
from app.models.user import User


def register_review_tools(
    registry: ToolRegistry,
    db: AsyncSession,
    current_user: User,
    *,
    tool_names: Iterable[str] | None = None,
) -> None:
    selected = set(tool_names or ())

    def include(name: str) -> bool:
        return not selected or name in selected

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

    async def review_multimodal_asset_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.services.multimodal_review_service import MultimodalReviewService

        asset_id = UUID(str(arguments["asset_id"]))
        result = await MultimodalReviewService(db).review_asset(asset_id, current_user.id)
        return ToolExecutionResult(
            output=result,
            evidence=[f"多模态审核完成，risk={result['risk_level']}，引用 {result['citation_count']} 条", *(result.get("issues") or [])],
            artifact_refs=[{"type": "media_review", "asset_id": result["asset_id"], "risk_level": result["risk_level"], "passed": result["passed"]}],
        )

    if include("review_artifacts"):
        register_tool(registry, "review_artifacts", "审查生成内容的来源、幻觉和风险。", "ReviewAgent", {"content": {"type": "string"}}, ["content"], review_artifacts)
    if include("review_multimodal_asset"):
        register_tool(registry, "review_multimodal_asset", "审核图片、视频、互动课件等多模态产物的事实依据、安全风险、版权风险与可访问性。", "ReviewAgent", {"asset_id": {"type": "string", "minLength": 1}}, ["asset_id"], review_multimodal_asset_handler)
