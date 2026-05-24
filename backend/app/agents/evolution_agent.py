from __future__ import annotations

import json
import logging

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.registry import AgentRegistry
from app.llm import ChatMessage, get_llm_provider
from app.services.prompt_service import PromptService

logger = logging.getLogger(__name__)


@AgentRegistry.register
class EvolutionAgent(BaseAgent):
    name = "EvolutionAgent"
    description = "分析学习数据，生成自进化策略建议"

    async def run(self, context: AgentContext) -> AgentResult:
        evidence = context.params.get("evidence", "")
        if not evidence:
            return self.error_result(message="缺少 evidence 参数")

        prompts = PromptService(self.db)
        rendered = await prompts.render_prompt(
            agent_name="EvolutionAgent",
            scene="evolution.analyze",
            params={"evidence": evidence[:4000]},
        )

        llm = get_llm_provider(
            db=self.db,
            user_id=context.user_id,
            course_id=context.course_id,
            agent_run_id=context.run_id,
        )
        response = await llm.chat(
            [ChatMessage(role="user", content=rendered.content)],
            temperature=0.3,
            max_tokens=3000,
        )

        strategies = self._parse_strategies(response.content)

        return self.success_result(
            data={"strategies": strategies, "raw_response": response.content},
            message="自进化策略分析完成",
            evidence=[evidence[:200]],
        )

    def _parse_strategies(self, content: str) -> list[dict]:
        """尝试从 LLM 响应中解析结构化策略列表"""
        try:
            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except (json.JSONDecodeError, ValueError):
            pass

        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                obj = json.loads(content[start:end])
                if isinstance(obj, dict):
                    strategies = obj.get("strategies", [])
                    if isinstance(strategies, list):
                        return strategies
                    return [obj]
        except (json.JSONDecodeError, ValueError):
            pass

        logger.warning("EvolutionAgent: 无法解析结构化策略，返回默认策略")
        return [
            {
                "strategy_type": "recommendation",
                "before_value": {},
                "after_value": {"summary": content[:500]},
                "description": content[:300],
                "risk_level": "medium",
            }
        ]
