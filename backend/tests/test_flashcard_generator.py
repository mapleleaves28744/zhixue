from __future__ import annotations

import json

import pytest

from app.generators.flashcard import FlashcardGenerator
from app.llm.schemas import ChatResponse


class VerboseFlashcardProvider:
    async def chat(self, messages, **kwargs):
        generic = {
            "cards": [{"front": "通用题", "back": "通用答", "hint": "通用提示"}] * 8,
        }
        requested = {
            "cards": [
                {
                    "front": f"二叉树遍历题 {index}",
                    "back": f"答案 {index}",
                    "hint": f"提示 {index}",
                    "knowledge_point": "二叉树遍历",
                }
                for index in range(1, 13)
            ]
        }
        return ChatResponse(
            content=(
                "下面先给通用卡片：\n"
                + json.dumps(generic, ensure_ascii=False)
                + "\n再给本次要求的卡片：\n"
                + json.dumps(requested, ensure_ascii=False)
            ),
            model="test-model",
        )


@pytest.mark.asyncio
async def test_flashcard_generator_keeps_only_requested_json_card_set() -> None:
    result = await FlashcardGenerator().generate(
        knowledge_name="二叉树遍历",
        context="前序、中序、后序与层序遍历。",
        requirement="生成 12 张个性化复习卡。",
        llm_provider=VerboseFlashcardProvider(),
    )

    content = json.loads(result.content)

    assert len(content["cards"]) == 12
    assert content["cards"][0]["front"] == "二叉树遍历题 1"
    assert "下面先给" not in result.content


@pytest.mark.asyncio
async def test_flashcard_generator_discards_incomplete_final_card() -> None:
    truncated = (
        '{"cards": ['
        '{"front":"题 1","back":"答 1","hint":"提示 1"},'
        '{"front":"题 2","back":"答 2","hint":"提示 2"},'
        '{"front":"题 3","back":"未完成'
    )

    class TruncatedProvider:
        async def chat(self, messages, **kwargs):
            return ChatResponse(content=truncated, model="test-model")

    result = await FlashcardGenerator().generate(
        knowledge_name="二叉树遍历",
        context="前序、中序、后序与层序遍历。",
        requirement="生成 3 张个性化复习卡。",
        llm_provider=TruncatedProvider(),
    )

    content = json.loads(result.content)

    assert [card["front"] for card in content["cards"]] == ["题 1", "题 2"]
