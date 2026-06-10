from __future__ import annotations

import json
import logging

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.registry import AgentRegistry
from app.agents.structured_chat_utils import call_structured_chat_or_none
from app.agents.structured_outputs import ReviewOutput
from app.llm import ChatMessage, get_llm_provider
from app.services.content_safety_service import ContentSafetyService
from app.services.prompt_service import PromptService

logger = logging.getLogger(__name__)

VALID_RISK_LEVELS = {"low", "medium", "high"}
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


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
        messages = [ChatMessage(role="user", content=rendered.content)]
        structured = await call_structured_chat_or_none(
            llm,
            messages,
            ReviewOutput,
            temperature=0.3,
            max_tokens=2048,
        )
        if structured is not None:
            review = structured.to_dict()
        else:
            response = await llm.chat(messages, temperature=0.3, max_tokens=2048)
            review = self._parse_review(response.content)
        safety = await ContentSafetyService().check(
            str(content),
            citations=context.params.get("citations") or [],
            source_chunks=context.params.get("source_chunks"),
            require_citation=bool(context.params.get("require_citation")),
        )
        review = self._merge_safety_review(review, safety)

        return self.success_result(
            data=review,
            message="内容审查完成",
        )

    def _merge_safety_review(self, review: dict, safety: dict) -> dict:
        if safety.get("safe", True):
            return review
        merged = dict(review)
        current_risk = str(merged.get("risk_level") or "medium")
        safety_risk = str(safety.get("risk_level") or "medium")
        if current_risk not in VALID_RISK_LEVELS:
            current_risk = "medium"
        if safety_risk not in VALID_RISK_LEVELS:
            safety_risk = "medium"
        merged["risk_level"] = (
            current_risk
            if RISK_ORDER[current_risk] >= RISK_ORDER[safety_risk]
            else safety_risk
        )
        merged["issues"] = list(merged.get("issues") or []) + list(safety.get("issues") or [])
        suggestions = merged.get("revision_suggestions")
        if isinstance(suggestions, list):
            merged["revision_suggestions"] = suggestions + list(safety.get("suggestions") or [])
        else:
            merged["revision_suggestions"] = "\n".join(
                item
                for item in [str(suggestions or ""), *[str(s) for s in safety.get("suggestions") or []]]
                if item
            )
        merged["pass"] = False
        return merged

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
