from __future__ import annotations

import json
import re
from typing import Any

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.registry import AgentRegistry
from app.llm import ChatMessage, get_llm_provider


@AgentRegistry.register
class KnowledgeGraphAgent(BaseAgent):
    name = "KnowledgeGraphAgent"
    description = "从对话文本抽取知识点实体与关系"

    async def run(self, context: AgentContext) -> AgentResult:
        dialogue = str(context.params.get("dialogue_text") or "").strip()
        if not dialogue:
            return self.error_result(message="缺少 dialogue_text")

        llm = get_llm_provider(db=self.db, user_id=context.user_id, course_id=context.course_id)
        prompt = (
            "从以下学习对话中抽取知识点实体与关系。只返回 JSON：\n"
            '{"entities":[{"name":"知识点名","description":"简述","understood":false}],'
            '"relations":[{"source":"A","target":"B","relation_type":"prerequisite|similar|used_in|confused_with","evidence":"依据"}]}\n\n'
            f"对话：\n{dialogue[:4000]}"
        )
        response = await llm.chat([ChatMessage(role="user", content=prompt)], temperature=0.2, max_tokens=2048)
        data = self._parse_json(response.content)
        if not isinstance(data, dict):
            return self.error_result(message="LLM 返回无法解析")
        return self.success_result(
            data={
                "entities": data.get("entities") or [],
                "relations": data.get("relations") or [],
            },
            message="对话知识图谱抽取成功",
        )

    def _parse_json(self, text: str) -> object:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None
