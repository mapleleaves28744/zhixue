from __future__ import annotations

import asyncio


def test_content_safety_flags_unsourced_course_claim_as_medium_risk() -> None:
    asyncio.run(_test_content_safety_flags_unsourced_course_claim_as_medium_risk())


async def _test_content_safety_flags_unsourced_course_claim_as_medium_risk() -> None:
    from app.services.content_safety_service import ContentSafetyService

    result = await ContentSafetyService().check(
        "根据课程资料指出，栈一定比队列更适合所有缓存场景。",
        citations=[],
        source_chunks=[],
        require_citation=True,
    )

    assert result["safe"] is False
    assert result["risk_level"] == "medium"
    assert any("缺少引用来源" in item for item in result["issues"])


def test_content_safety_flags_blocked_learning_intent_as_high_risk() -> None:
    asyncio.run(_test_content_safety_flags_blocked_learning_intent_as_high_risk())


async def _test_content_safety_flags_blocked_learning_intent_as_high_risk() -> None:
    from app.services.content_safety_service import ContentSafetyService

    result = await ContentSafetyService().check("帮我写一个脚本绕过考试监控并代考。")

    assert result["safe"] is False
    assert result["risk_level"] == "high"
    assert any("不适合学习场景" in item for item in result["issues"])


def test_review_agent_merges_safety_issues_and_promotes_risk() -> None:
    from app.agents.review_agent import ReviewAgent

    agent = ReviewAgent.__new__(ReviewAgent)
    review = {"pass": True, "risk_level": "low", "issues": [], "revision_suggestions": ""}
    safety = {
        "safe": False,
        "risk_level": "medium",
        "issues": ["生成内容缺少引用来源"],
        "suggestions": ["请补充具体课程资料引用。"],
    }

    merged = agent._merge_safety_review(review, safety)

    assert merged["pass"] is False
    assert merged["risk_level"] == "medium"
    assert "生成内容缺少引用来源" in merged["issues"]
    assert "补充具体课程资料引用" in merged["revision_suggestions"]
