from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.registry import AgentRegistry
from app.llm import ChatMessage, get_llm_provider
from app.services.prompt_service import PromptService

logger = logging.getLogger(__name__)


class PathCandidate(BaseModel):
    """LLM 评估的学习路径候选方案。"""
    name: str = Field(description="方案名称")
    coverage_score: float = Field(description="知识覆盖度 0-1")
    difficulty_gradient_score: float = Field(description="难度梯度合理性 0-1")
    time_fit_score: float = Field(description="时间适配度 0-1")
    total_score: float = Field(description="综合评分 0-1")
    reason: str = Field(description="评分理由")
    items: list[dict[str, Any]] = Field(description="学习步骤列表")


@AgentRegistry.register
class PlannerAgent(BaseAgent):
    name = "PlannerAgent"
    description = "生成个性化学习计划（多目标优化）"

    async def run(self, context: AgentContext) -> AgentResult:
        student_profile = context.params.get("student_profile", "")
        learning_goal = context.params.get("learning_goal", "")
        if not learning_goal:
            return self.error_result(message="缺少 learning_goal 参数")

        knowledge_points = context.params.get("knowledge_points", [])
        weak_points = context.params.get("weak_points", [])
        mastery_snapshot = context.params.get("mastery_snapshot", {})
        target_knowledge_ids = set(context.params.get("target_knowledge_ids", []))
        available_time = context.params.get("available_time", "每天1小时")
        difficulty = context.params.get("difficulty", "medium")

        # 生成多条候选路径
        candidates = self._generate_candidates(
            knowledge_points=knowledge_points,
            weak_points=weak_points,
            mastery_snapshot=mastery_snapshot,
            target_knowledge_ids=target_knowledge_ids,
            learning_goal=learning_goal,
            difficulty=difficulty,
        )

        # 如果有 LLM，用 LLM 综合评估择优
        best_items = candidates[0]["items"] if candidates else []
        best_reason = "基于规则引擎生成"

        if len(candidates) > 1:
            llm_result = await self._llm_evaluate_paths(
                context=context,
                candidates=candidates,
                student_profile=student_profile,
                learning_goal=learning_goal,
                available_time=available_time,
            )
            if llm_result:
                best_items = llm_result.get("items", best_items)
                best_reason = llm_result.get("reason", best_reason)

        return self.success_result(
            data={
                "reason": best_reason,
                "items": best_items,
                "candidates_count": len(candidates),
                "difficulty": difficulty,
            },
            message="学习计划生成完成",
        )

    def _generate_candidates(
        self,
        *,
        knowledge_points: list[dict[str, Any]],
        weak_points: list[Any],
        mastery_snapshot: dict[str, Any],
        target_knowledge_ids: set[str],
        learning_goal: str,
        difficulty: str,
    ) -> list[dict[str, Any]]:
        """生成多条候选路径，按不同优化目标排序。"""
        weak_names = {str(item.get("name", item)).lower() for item in weak_points if item}

        def mastery_for(point: dict[str, Any]) -> float:
            value = mastery_snapshot.get(point.get("id"), mastery_snapshot.get(point.get("name"), 0.6))
            try:
                number = float(value)
                if number > 1:
                    number /= 100
                return max(0.0, min(1.0, number))
            except (TypeError, ValueError):
                return 0.6

        def build_items(sorted_points: list[dict[str, Any]], label: str) -> dict[str, Any]:
            selected = sorted_points[:5]
            items: list[dict[str, Any]] = []
            for index, point in enumerate(selected, start=1):
                name = str(point.get("name") or f"知识点 {index}")
                mastery = mastery_for(point)
                action = self._pick_action(mastery, name in weak_names)
                items.append({
                    "knowledge_id": point.get("id"),
                    "title": f"{action}：{name}",
                    "item_type": self._action_to_type(action),
                    "order_index": index,
                    "estimated_minutes": 20 + index * 5,
                    "mastery_level": round(mastery, 2),
                    "reason": f"当前掌握度 {mastery:.0%}，{action}优先。",
                })
            # 计算各维度得分
            coverage = len({i.get("knowledge_id") for i in items if i.get("knowledge_id")}) / max(1, len(knowledge_points))
            weak_covered = sum(1 for i in items if any(w in i.get("title", "") for w in weak_names))
            gradient = self._difficulty_gradient_score(items, mastery_snapshot)
            return {
                "name": label,
                "items": items,
                "coverage_score": round(min(1.0, coverage), 2),
                "difficulty_gradient_score": gradient,
                "weak_covered": weak_covered,
            }

        # 策略 1：薄弱优先 — 弱点排前面
        weak_first = sorted(
            knowledge_points,
            key=lambda p: (0 if str(p.get("name", "")).lower() in weak_names else 1, mastery_for(p)),
        )
        # 策略 2：覆盖优先 — 按 sort_order 尽量覆盖更多知识点
        coverage_first = sorted(
            knowledge_points,
            key=lambda p: (int(p.get("sort_order") or 0), mastery_for(p)),
        )
        # 策略 3：难度梯度 — 从低掌握度到高掌握度
        gradient_first = sorted(knowledge_points, key=lambda p: mastery_for(p))

        return [
            build_items(weak_first, "薄弱优先"),
            build_items(coverage_first, "覆盖优先"),
            build_items(gradient_first, "难度梯度优先"),
        ]

    def _build_rule_items(
        self,
        *,
        knowledge_points: list[dict[str, Any]],
        weak_points: list[Any],
        mastery_snapshot: dict[str, Any],
        target_knowledge_ids: set[str],
        learning_goal: str,
        difficulty: str = "medium",
    ) -> list[dict[str, Any]]:
        """规则引擎单路径（兼容旧接口与单元测试）。"""
        if not knowledge_points:
            return []
        points = knowledge_points
        if target_knowledge_ids:
            filtered = [
                point for point in knowledge_points
                if str(point.get("id")) in target_knowledge_ids
            ]
            if filtered:
                points = filtered
        candidates = self._generate_candidates(
            knowledge_points=points,
            weak_points=weak_points,
            mastery_snapshot=mastery_snapshot,
            target_knowledge_ids=target_knowledge_ids,
            learning_goal=learning_goal,
            difficulty=difficulty,
        )
        return candidates[0]["items"] if candidates else []

    def _difficulty_gradient_score(
        self,
        items: list[dict[str, Any]],
        mastery_snapshot: dict[str, Any],
    ) -> float:
        """评估路径的难度梯度合理性：从低到高排列得分更高。"""
        if len(items) < 2:
            return 1.0
        levels = [i.get("mastery_level", 0.5) for i in items]
        increasing = sum(1 for a, b in zip(levels, levels[1:]) if b >= a)
        return round(increasing / (len(levels) - 1), 2)

    async def _llm_evaluate_paths(
        self,
        *,
        context: AgentContext,
        candidates: list[dict[str, Any]],
        student_profile: str,
        learning_goal: str,
        available_time: str,
    ) -> dict[str, Any] | None:
        """用 LLM 综合评估候选路径，选择最优方案。"""
        try:
            llm = get_llm_provider(
                db=self.db,
                user_id=context.user_id,
                course_id=context.course_id,
                agent_run_id=context.run_id,
            )

            candidate_summary = "\n".join(
                f"方案 {i + 1}（{c['name']}）：覆盖度={c['coverage_score']}，"
                f"难度梯度={c['difficulty_gradient_score']}，"
                f"薄弱覆盖={c['weak_covered']}，"
                f"步骤={[item['title'] for item in c['items']]}"
                for i, c in enumerate(candidates)
            )

            prompt = (
                f"学生画像：{student_profile[:500]}\n"
                f"学习目标：{learning_goal}\n"
                f"可用时间：{available_time}\n\n"
                f"以下是三条候选学习路径方案：\n{candidate_summary}\n\n"
                "请评估每条方案，选出最优方案并说明理由。返回 JSON：\n"
                '{"selected_index": 0, "reason": "选择理由", '
                '"items": [选中方案的步骤列表原样返回]}'
            )

            response = await llm.chat(
                [ChatMessage(role="user", content=prompt)],
                temperature=0.3,
                max_tokens=2048,
            )

            import json
            cleaned = response.content.strip()
            if cleaned.startswith("```"):
                lines = [l for l in cleaned.splitlines() if not l.strip().startswith("```")]
                cleaned = "\n".join(lines).strip()

            data = json.loads(cleaned)
            idx = int(data.get("selected_index", 0))
            if 0 <= idx < len(candidates):
                return {
                    "items": candidates[idx]["items"],
                    "reason": data.get("reason", f"LLM 选择方案 {idx + 1}"),
                }
        except Exception as exc:
            logger.warning("PlannerAgent LLM evaluation failed, using rule-based: %s", exc)

        return None

    @staticmethod
    def _pick_action(mastery: float, is_weak: bool) -> str:
        if is_weak or mastery < 0.4:
            return "复习"
        if mastery < 0.7:
            return "学习"
        if mastery < 0.9:
            return "练习"
        return "拓展"

    @staticmethod
    def _action_to_type(action: str) -> str:
        mapping = {"复习": "review", "学习": "learn", "练习": "practice", "总结": "summary", "拓展": "learn"}
        return mapping.get(action, "learn")
