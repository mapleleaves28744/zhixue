"""复习卡（Flashcard）生成器。"""
from __future__ import annotations

import json
from typing import Any

from app.generators.base import BaseGenerator, GeneratorResult
from app.llm import ChatMessage
from app.services.generator_registry import GeneratorRegistry


@GeneratorRegistry.register
class FlashcardGenerator(BaseGenerator):
    resource_type = "flashcard"
    display_name = "复习卡"

    async def generate(
        self,
        *,
        knowledge_name: str,
        context: str,
        profile_text: str = "",
        requirement: str = "",
        llm_provider: Any = None,
        **kwargs: Any,
    ) -> GeneratorResult:
        prompt = (
            f"请围绕知识点「{knowledge_name}」生成一组复习卡（5-8 张）。\n\n"
            f"参考资料：\n{context[:2000]}\n\n"
            f"学生画像：{profile_text[:500]}\n\n"
            f"额外要求：{requirement or '无'}\n\n"
            '返回 JSON 格式：\n'
            '{"cards": [{"front": "问题", "back": "答案", "hint": "提示"}]}'
        )

        if llm_provider is None:
            return GeneratorResult(
                content=json.dumps({"cards": [
                    {"front": f"什么是{knowledge_name}？", "back": "（LLM 未连接）", "hint": ""},
                ]}, ensure_ascii=False),
                title=f"{knowledge_name}复习卡",
                resource_type=self.resource_type,
            )

        response = await llm_provider.chat(
            [ChatMessage(role="user", content=prompt)],
            temperature=0.5,
            max_tokens=2048,
        )

        return GeneratorResult(
            content=response.content,
            title=f"{knowledge_name}复习卡",
            resource_type=self.resource_type,
            metadata={"model": response.model, "format": "flashcard_json"},
        )
