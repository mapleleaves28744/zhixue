from __future__ import annotations

from uuid import UUID

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.registry import AgentRegistry
from app.services.knowledge_service import KnowledgeService


@AgentRegistry.register
class KnowledgeAgent(BaseAgent):
    name = "KnowledgeAgent"
    description = "从课程资料中提取知识点"

    async def run(self, context: AgentContext) -> AgentResult:
        material_id = context.params.get("material_id")
        if not material_id:
            return self.error_result(message="缺少 material_id 参数")

        service = KnowledgeService(self.db)
        try:
            points = await service.extract_from_material(UUID(str(material_id)))
        except Exception as exc:
            return self.error_result(message=f"知识点提取失败: {exc}")

        return self.success_result(
            data={
                "knowledge_points": [
                    {"id": str(p.id), "name": p.name, "description": p.description}
                    for p in points
                ],
                "count": len(points),
            },
            message=f"提取了 {len(points)} 个知识点",
            evidence=[f"从资料 {material_id} 的 {len(points)} 个切片中提取"],
        )
