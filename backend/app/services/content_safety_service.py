from __future__ import annotations

from typing import Any


class ContentSafetyService:
    """Rule-based safety and grounding checks for generated learning content."""

    BLOCKED_INTENT_PATTERNS = (
        "绕过考试监控",
        "代考",
        "窃取账号",
        "泄露隐私",
        "破解密码",
    )

    UNSOURCED_CLAIM_MARKERS = (
        "据研究表明",
        "根据统计",
        "专家指出",
        "权威数据显示",
        "大量实验表明",
    )

    async def check(
        self,
        content: str,
        *,
        citations: list[dict[str, Any]] | None = None,
        source_chunks: list[dict[str, Any]] | None = None,
        require_citation: bool = False,
    ) -> dict[str, Any]:
        issues: list[str] = []
        suggestions: list[str] = []
        citations = citations or []

        for pattern in self.BLOCKED_INTENT_PATTERNS:
            if pattern in content:
                issues.append(f"检测到不适合学习场景的请求或内容: {pattern}")
                suggestions.append("请拒绝该部分内容，并改为提供合规学习建议。")

        for marker in self.UNSOURCED_CLAIM_MARKERS:
            if marker in content:
                issues.append(f"疑似无来源学术声称: {marker}")
                suggestions.append("请补充具体课程资料引用，或标注“AI 推断内容，建议核对资料”。")

        if require_citation and not citations:
            issues.append("生成内容缺少引用来源")
            suggestions.append("请基于 RAG/Wiki 重新生成，或明确标注无可靠来源。")

        source_chunks = source_chunks if source_chunks is not None else None
        if source_chunks == [] and any(marker in content for marker in ("根据课程", "资料指出", "课本")):
            issues.append("声称引用课程资料但未提供来源引用")
            suggestions.append("请添加具体 chunk 引用或标注“AI 推断内容，建议核对资料”。")

        risk_level = "high" if any("不适合学习场景" in item for item in issues) else "medium" if issues else "low"
        return {
            "safe": not issues,
            "risk_level": risk_level,
            "issues": issues,
            "suggestions": suggestions,
        }
