from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from app.agents.structured_chat_utils import call_structured_chat
from app.agents.structured_outputs import (
    EvolutionAnalysisOutput,
    MemoryReflectOutput,
    ProfileRebuildOutput,
    QuizGenerationOutput,
    ReviewOutput,
)
from app.llm.adapters.mock_provider import MockLLMProvider
from app.llm.schemas import ChatMessage


@pytest.mark.parametrize(
    ("schema", "prompt_hint"),
    [
        (QuizGenerationOutput, "Quiz Agent 结构化练习题 栈 数量：2"),
        (ReviewOutput, "ReviewAgent 审查内容"),
        (EvolutionAnalysisOutput, "EvolutionAgent 自进化 栈"),
        (MemoryReflectOutput, "学习分析引擎 长期记忆 栈"),
        (ProfileRebuildOutput, "学习分析引擎 学生画像 栈"),
    ],
)
def test_mock_provider_structured_chat_validates_schemas(schema, prompt_hint: str) -> None:
    asyncio.run(_test_mock_provider_structured_chat_validates_schemas(schema, prompt_hint))


async def _test_mock_provider_structured_chat_validates_schemas(schema, prompt_hint: str) -> None:
    provider = MockLLMProvider()
    result = await call_structured_chat(
        provider,
        [ChatMessage(role="user", content=prompt_hint)],
        schema,
        max_retries=0,
    )
    assert result is not None
    if schema is QuizGenerationOutput:
        assert len(result.questions) >= 1
    elif schema is ReviewOutput:
        assert result.risk_level in {"low", "medium", "high"}
    elif schema is EvolutionAnalysisOutput:
        assert len(result.strategies) >= 1
    elif schema is MemoryReflectOutput:
        assert len(result.memories) >= 1
    elif schema is ProfileRebuildOutput:
        assert result.profile_summary


def test_review_output_to_dict_uses_pass_alias() -> None:
    payload = ReviewOutput.model_validate(
        {
            "pass": False,
            "risk_level": "high",
            "issues": ["缺少引用"],
            "revision_suggestions": ["补充来源"],
        }
    )
    data = payload.to_dict()
    assert data["pass"] is False
    assert data["risk_level"] == "high"
    assert "缺少引用" in data["issues"]


def test_evolution_analysis_rejects_empty_strategy_list() -> None:
    with pytest.raises(ValidationError):
        EvolutionAnalysisOutput.model_validate({"strategies": []})
