from __future__ import annotations

from app.services.knowledge_graph_service import KnowledgeGraphService


def test_rule_extract_finds_data_structure_terms() -> None:
    svc = KnowledgeGraphService.__new__(KnowledgeGraphService)
    entities, relations = svc._rule_extract("请解释二叉树与 BFS 的区别，以及动态规划入门。")
    names = {item["name"] for item in entities}
    assert "二叉树" in names
    assert "BFS" in names
    assert "动态规划" in names
    assert isinstance(relations, list)
