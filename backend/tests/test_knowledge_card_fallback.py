"""知识卡片：文生图 / Mermaid 兜底策略。"""

from __future__ import annotations

from app.llm.multimodal_provider import MockMultimodalProvider, uses_real_image_generation
from app.services.diagram_service import CONCISE_IMAGE_CARD_RULES, CONCISE_MERMAID_RULES
from app.services.multimodal_resource_service import mermaid_fallback_depth, mermaid_fallback_kind


def test_uses_real_image_generation_false_for_mock() -> None:
    assert uses_real_image_generation(MockMultimodalProvider()) is False


def test_concise_rules_present_in_prompt_constants() -> None:
    assert "10 个汉字" in CONCISE_MERMAID_RULES
    assert "3–4 个视觉元素" in CONCISE_IMAGE_CARD_RULES


def test_mermaid_fallback_routing() -> None:
    assert mermaid_fallback_kind("process_visual") == "diagram"
    assert mermaid_fallback_kind("concept_illustration") == "mindmap"
    assert mermaid_fallback_depth(None) == 3
    assert mermaid_fallback_depth("请多层展开复杂结构") == 4
