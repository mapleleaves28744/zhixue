from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.repositories.media_repository import MediaRepository
from app.services.content_safety_service import ContentSafetyService
from app.services.courseware_service import CoursewareService


class MultimodalReviewService:
    """规则优先的多模态产物审核：引用、Prompt 安全、课件 spec、可访问性。"""

    IMAGE_PROMPT_RISKS = (
        "真实人物",
        "名人",
        "商标",
        "logo",
        "医疗承诺",
        "政治宣传",
        "裸体",
        "暴力血腥",
    )

    HTML_ASSET_TYPES = {"courseware", "storyboard", "html"}

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.media = MediaRepository(db)

    async def review_asset(self, asset_id: UUID, user_id: UUID) -> dict[str, Any]:
        asset = await self.media.get_asset_for_user(asset_id, user_id)
        if asset is None:
            raise BusinessException(code=ErrorCode.NOT_FOUND, detail="媒体资产不存在", status_code=404)

        issues: list[str] = []
        suggestions: list[str] = []
        citations = list(asset.citations or [])

        if not citations:
            issues.append("多模态产物缺少课程资料引用")
            suggestions.append("请基于 search_course_knowledge 结果重新生成，或标注 AI 推断内容。")

        prompt_text = " ".join(filter(None, [asset.prompt, asset.description, asset.title]))
        for pattern in self.IMAGE_PROMPT_RISKS:
            if pattern.lower() in prompt_text.lower():
                issues.append(f"Prompt/描述包含高风险关键词: {pattern}")
                suggestions.append("请移除真实人物、商标或敏感承诺类描述后重试。")

        if asset.asset_type in self.HTML_ASSET_TYPES or str(asset.mime_type or "").startswith("text/html"):
            spec = (asset.render_meta or {}).get("spec")
            if isinstance(spec, dict):
                spec_safety = CoursewareService().validate_spec(spec)
                if not spec_safety.get("passed"):
                    issues.extend([f"课件 spec: {item}" for item in spec_safety.get("issues") or []])
                    suggestions.append("仅允许 JSON spec + 服务端模板渲染，禁止外链脚本。")
            else:
                issues.append("HTML 类产物缺少可审计的 spec 元数据")
                suggestions.append("请通过 generate_interactive_courseware / generate_storyboard_html 生成。")

        if asset.asset_type == "video":
            render_meta = asset.render_meta or {}
            if not citations and not render_meta.get("storyboard_asset_id"):
                issues.append("视频产物缺少分镜/字幕依据")
                suggestions.append("优先使用 storyboard + 本地 MoviePy 合成，避免黑盒 T2V 作为事实主体。")

        content_check = await ContentSafetyService().check(
            prompt_text,
            citations=citations,
            require_citation=asset.asset_type in {"image", "video", "courseware", "storyboard"},
        )
        issues.extend(content_check.get("issues") or [])
        suggestions.extend(content_check.get("suggestions") or [])

        risk_level = "high" if any("高风险" in item or "不适合" in item for item in issues) else (
            "medium" if issues else "low"
        )
        if content_check.get("risk_level") == "high":
            risk_level = "high"
        elif content_check.get("risk_level") == "medium" and risk_level == "low":
            risk_level = "medium"

        result: dict[str, Any] = {
            "asset_id": str(asset.id),
            "asset_type": asset.asset_type,
            "title": asset.title,
            "passed": risk_level == "low",
            "risk_level": risk_level,
            "issues": issues,
            "suggestions": suggestions,
            "citation_count": len(citations),
            "requires_confirmation": risk_level in {"medium", "high"},
            "reviewer": "MultimodalReviewService",
        }
        await self.media.update_asset(asset, safety_result=result)
        await self.db.commit()
        await self.db.refresh(asset)
        return result
