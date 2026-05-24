from __future__ import annotations

from typing import Any

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.registry import AgentRegistry
from app.llm import ChatMessage, get_llm_provider
from app.services.prompt_service import PromptService


@AgentRegistry.register
class PlannerAgent(BaseAgent):
    name = "PlannerAgent"
    description = "生成个性化学习计划"

    async def run(self, context: AgentContext) -> AgentResult:
        student_profile = context.params.get("student_profile", "")
        learning_goal = context.params.get("learning_goal", "")
        if not learning_goal:
            return self.error_result(message="缺少 learning_goal 参数")
        knowledge_points = context.params.get("knowledge_points", [])
        weak_points = context.params.get("weak_points", [])
        mastery_snapshot = context.params.get("mastery_snapshot", {})
        target_knowledge_ids = set(context.params.get("target_knowledge_ids", []))

        items = self._build_rule_items(
            knowledge_points=knowledge_points,
            weak_points=weak_points,
            mastery_snapshot=mastery_snapshot,
            target_knowledge_ids=target_knowledge_ids,
            learning_goal=learning_goal,
        )

        prompts = PromptService(self.db)
        rendered = await prompts.render_prompt(
            agent_name="PlannerAgent",
            scene="plan.learning",
            params={
                "student_profile": student_profile,
                "learning_goal": learning_goal,
                "available_time": context.params.get("available_time", "每天1小时"),
            },
        )

        llm = get_llm_provider(
            db=self.db,
            user_id=context.user_id,
            course_id=context.course_id,
            agent_run_id=context.run_id,
        )
        response = await llm.chat(
            [ChatMessage(role="user", content=rendered.content)],
            temperature=0.7,
            max_tokens=512,
        )

        return self.success_result(
            data={
                "reason": response.content.strip(),
                "items": items,
                "learning_plan": response.content.strip(),
            },
            message="学习计划生成完成",
        )

    def _build_rule_items(
        self,
        *,
        knowledge_points: list[dict[str, Any]],
        weak_points: list[Any],
        mastery_snapshot: dict[str, Any],
        target_knowledge_ids: set[str],
        learning_goal: str,
    ) -> list[dict[str, Any]]:
        weak_names = {str(item.get("name", item)).lower() for item in weak_points if item}

        def mastery_for(point: dict[str, Any]) -> int:
            value = mastery_snapshot.get(point.get("id"), mastery_snapshot.get(point.get("name"), 60))
            try:
                number = float(value)
                if number <= 1:
                    number *= 100
                return max(0, min(100, int(number)))
            except (TypeError, ValueError):
                return 60

        def score(point: dict[str, Any]) -> tuple[int, int, int, int, str]:
            name = str(point.get("name", ""))
            return (
                0 if str(point.get("id")) in target_knowledge_ids else 1,
                0 if name.lower() in weak_names or name in learning_goal else 1,
                mastery_for(point),
                int(point.get("sort_order") or 0),
                name,
            )

        selected = sorted(knowledge_points, key=score)[:5]
        actions = ["复习", "学习", "练习", "总结", "拓展"]
        types = ["review", "learn", "practice", "summary", "learn"]
        items: list[dict[str, Any]] = []
        for index, point in enumerate(selected, start=1):
            name = str(point.get("name") or f"知识点 {index}")
            mastery = mastery_for(point)
            items.append(
                {
                    "knowledge_id": point.get("id"),
                    "title": f"{actions[min(index - 1, len(actions) - 1)]}：{name}",
                    "item_type": types[min(index - 1, len(types) - 1)],
                    "order_index": index,
                    "estimated_minutes": 25 + index * 5,
                    "reason": f"当前掌握度约 {mastery}%，结合目标和薄弱点优先安排。",
                }
            )
        return items
