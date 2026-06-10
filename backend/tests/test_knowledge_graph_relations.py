"""知识点关系推断与图谱边方向测试。"""

from __future__ import annotations

from app.services.knowledge_graph_service import KnowledgeGraphService
from app.services.wiki_graph_service import WikiGraphService


def test_rule_infer_material_relations_builds_next_chain() -> None:
    svc = KnowledgeGraphService.__new__(KnowledgeGraphService)

    class KP:
        def __init__(self, name: str, chapter: str, sort_order: int = 0) -> None:
            self.name = name
            self.chapter = chapter
            self.sort_order = sort_order

    points = [KP("线性表", "第2章"), KP("栈", "第2章", 1), KP("队列", "第2章", 2)]
    relations = svc._rule_infer_material_relations(points[:1], points, "栈与队列对比")
    types = {(r["source"], r["target"], r["relation_type"]) for r in relations}
    assert ("线性表", "栈", "next") in types
    assert ("栈", "队列", "next") in types


def test_format_link_direction() -> None:
    forward = WikiGraphService._format_link(
        link_id="1",
        source="a",
        target="b",
        relation_type="prerequisite",
        evidence="e",
        confidence=0.8,
        is_inferred=True,
        scope="personal",
        line_style="solid",
    )
    both = WikiGraphService._format_link(
        link_id="2",
        source="a",
        target="b",
        relation_type="similar",
        evidence="e",
        confidence=0.8,
        is_inferred=True,
        scope="personal",
        line_style="solid",
    )
    assert forward["direction"] == "forward"
    assert both["direction"] == "both"
