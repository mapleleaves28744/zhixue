from __future__ import annotations

import json
import logging

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.registry import AgentRegistry
from app.llm import ChatMessage, get_llm_provider
from app.services.prompt_service import PromptService

logger = logging.getLogger(__name__)

VALID_RISK_LEVELS = {"low", "medium", "high"}


@AgentRegistry.register
class ReviewAgent(BaseAgent):
    name = "ReviewAgent"
    description = "审查 AI 生成内容的质量和来源，审核策略风险等级"

    async def run(self, context: AgentContext) -> AgentResult:
        content = context.params.get("content") or context.metadata.get("wiki_content", "")
        if not content:
            return self.error_result(message="缺少待审查内容")

        prompts = PromptService(self.db)
        rendered = await prompts.render_prompt(
            agent_name="ReviewAgent",
            scene="review.check",
            params={"content": content[:4000]},
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
            max_tokens=2048,
        )

        review = self._parse_review(response.content)

        return self.success_result(
            data=review,
            message="内容审查完成",
        )

    def _parse_review(self, content: str) -> dict:
        """解析审查结果，提取风险等级和审核意见"""
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(content[start:end])
                risk = result.get("risk_level", "medium")
                if risk not in VALID_RISK_LEVELS:
                    risk = "medium"
                result["risk_level"] = risk
                return result
        except (json.JSONDecodeError, ValueError):
            pass

        risk_level = "medium"
        lower = content.lower()
        if "高风险" in content or "high" in lower:
            risk_level = "high"
        elif "低风险" in content or "low" in lower:
            risk_level = "low"

        return {
            "pass": True,
            "risk_level": risk_level,
            "issues": [],
            "revision_suggestions": content[:300],
        }
