"""资源多模态预览字段与 Mermaid 工具测试。"""

from __future__ import annotations

from app.services.resource_media_service import ResourceMediaService
from app.services.resource_service import ResourceService
from app.utils.mermaid_util import extract_mermaid_code, is_mermaid_code, repair_mermaid_content


def test_extract_mermaid_code_fallback_uses_double_root_parens() -> None:
    code = extract_mermaid_code("普通 Markdown 无 Mermaid", fallback_root="栈")
    assert code.startswith("mindmap")
    assert "root((栈))" in code
    assert "root(栈)" not in code.replace("root((栈))", "")


def test_extract_mermaid_code_from_fence() -> None:
    code = extract_mermaid_code("```mermaid\nmindmap\n  root(栈)\n    操作\n```", fallback_root="栈")
    assert code.startswith("mindmap")
    assert "root(栈)" in code


def test_is_mermaid_code_detects_flowchart() -> None:
    assert is_mermaid_code("flowchart TD\n  A --> B")
    assert not is_mermaid_code("# 普通 Markdown")


def test_repair_mermaid_content_from_hybrid_text() -> None:
    raw = (
        'mindmap root((理解 "线性表" <br> 的定义))\n'
        "**定义**\n"
        "  逻辑结构: 线性关系\n"
        "**操作**\n"
        "  插入删除: O(n)"
    )
    fixed = repair_mermaid_content(raw, root_label="线性表")
    assert fixed.startswith("mindmap")
    assert "root((" in fixed
    assert "定义" in fixed


def test_speech_text_from_markdown_strips_headings() -> None:
    text = ResourceMediaService._speech_text_from_markdown("## 栈\n\n- 后进先出\n\n用于函数调用。")
    assert "栈" in text
    assert "##" not in text


def test_resource_preview_mode_recognizes_video_asset() -> None:
    asset = type("Asset", (), {"asset_type": "video", "mime_type": "video/mp4"})()

    assert ResourceService._preview_mode("video", asset) == "video"
