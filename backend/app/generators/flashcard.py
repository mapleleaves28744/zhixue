"""复习卡（Flashcard）生成器。"""
from __future__ import annotations

import json
import re
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
        requested_count = _requested_card_count(requirement)
        prompt = (
            f"请围绕知识点「{knowledge_name}」生成一组复习卡（{requested_count} 张）。\n\n"
            f"参考资料：\n{context[:2000]}\n\n"
            f"学生画像：{profile_text[:500]}\n\n"
            f"额外要求：{requirement or '无'}\n\n"
            '每张卡片的答案和提示各不超过两句，避免长段文字。\n'
            '只返回一个 JSON 对象，不要输出 Markdown、说明文字、代码围栏或额外卡片。\n'
            '格式：\n'
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
            max_tokens=4096,
        )

        return GeneratorResult(
            content=_normalize_flashcard_json(response.content, requested_count=requested_count),
            title=f"{knowledge_name}复习卡",
            resource_type=self.resource_type,
            metadata={"model": response.model, "format": "flashcard_json"},
        )


def _requested_card_count(requirement: str) -> int:
    match = re.search(r"(\d{1,2})\s*张", requirement or "")
    if match:
        return max(1, min(20, int(match.group(1))))
    return 8


def _normalize_flashcard_json(content: str, *, requested_count: int) -> str:
    """从模型混入的说明文字中提取最符合本次数量的卡片 JSON。"""
    decoder = json.JSONDecoder()
    candidates: list[list[dict[str, Any]]] = []
    standalone_cards: list[dict[str, Any]] = []
    for index, char in enumerate(content):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(content[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "front" in parsed and "back" in parsed:
            front = str(parsed.get("front") or "").strip()
            back = str(parsed.get("back") or "").strip()
            if front and back:
                standalone_cards.append(
                    {
                        "front": front,
                        "back": back,
                        "hint": str(parsed.get("hint") or "").strip(),
                    }
                )
        cards = parsed.get("cards") if isinstance(parsed, dict) else None
        if isinstance(cards, list):
            normalized = [
                {
                    "front": str(card.get("front") or "").strip(),
                    "back": str(card.get("back") or "").strip(),
                    "hint": str(card.get("hint") or "").strip(),
                }
                for card in cards
                if isinstance(card, dict)
                and str(card.get("front") or "").strip()
                and str(card.get("back") or "").strip()
            ]
            if normalized:
                candidates.append(normalized)
    if not candidates and standalone_cards:
        return json.dumps({"cards": standalone_cards}, ensure_ascii=False)
    if not candidates:
        return content.strip()
    cards = min(
        candidates,
        key=lambda item: (0 if len(item) == requested_count else 1, abs(len(item) - requested_count), -len(item)),
    )
    return json.dumps({"cards": cards}, ensure_ascii=False)
