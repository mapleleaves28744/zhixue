from __future__ import annotations


def test_mindmap_service_extracts_fenced_mermaid_code() -> None:
    from app.services.mindmap_service import MindmapService

    service = MindmapService.__new__(MindmapService)
    code = service._extract_mermaid(
        "```mermaid\nmindmap\n  root(二叉树)\n    遍历\n```",
        topic="二叉树",
    )

    assert code.startswith("mindmap")
    assert "root(二叉树)" in code


def test_mindmap_service_builds_inference_citation_when_no_chunks() -> None:
    from app.services.mindmap_service import MindmapService

    service = MindmapService.__new__(MindmapService)
    citations = service._build_citations([], topic="图", scope="course", depth=3)

    assert citations[0]["source_type"] == "inference"
    assert citations[-1]["source_type"] == "generation_config"


def test_diagram_service_extracts_sequence_diagram_and_falls_back_by_type() -> None:
    from app.services.diagram_service import DiagramService

    service = DiagramService.__new__(DiagramService)
    extracted = service._extract_mermaid(
        "```mermaid\nsequenceDiagram\n  A->>B: 调用\n```",
        concept="递归",
        diagram_type="sequence",
    )
    fallback = service._extract_mermaid(
        "无法生成",
        concept="递归调用栈",
        diagram_type="sequence",
    )

    assert extracted.startswith("sequenceDiagram")
    assert fallback.startswith("sequenceDiagram")
    assert "递归调用栈" in fallback


def test_diagram_service_rejects_unknown_type_in_prompt_path_by_fallbacking_to_flowchart() -> None:
    from app.services.diagram_service import DIAGRAM_PROMPTS

    assert set(DIAGRAM_PROMPTS) == {"flowchart", "sequence", "class", "er"}
