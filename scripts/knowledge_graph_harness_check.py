#!/usr/bin/env python3
"""知识图谱双轨 Harness 冒烟验收：掌握度 + 图谱 API + 对话抽取规则。"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def check_imports() -> None:
    from app.main import app
    from app.rag.graph_retriever import GraphRetriever
    from app.services.chat_knowledge_pipeline import summarize_extract_for_ui
    from app.services.knowledge_graph_service import KnowledgeGraphService
    from app.services.mastery_service import MasteryService
    from app.services.wiki_graph_service import WikiGraphService

    assert app.title
    assert GraphRetriever and MasteryService and WikiGraphService
    assert KnowledgeGraphService and summarize_extract_for_ui
    print("OK imports")


def check_rule_extract() -> None:
    from app.services.knowledge_graph_service import KnowledgeGraphService

    svc = KnowledgeGraphService.__new__(KnowledgeGraphService)
    entities, _ = svc._rule_extract("请解释二叉树与 BFS")
    names = {e["name"] for e in entities}
    assert "二叉树" in names and "BFS" in names
    print("OK rule_extract")


def check_mastery_math() -> None:
    from app.services.mastery_service import MasteryService

    svc = MasteryService.__new__(MasteryService)
    score = 0.5
    up = min(1.0, score + svc.LEARN_RATE * (1.0 - score))
    down = max(0.0, score - svc.LEARN_RATE * 0.6)
    assert up > score > down
    print("OK mastery_math")


def check_ui_summary() -> None:
    from app.services.chat_knowledge_pipeline import summarize_extract_for_ui

    summary = summarize_extract_for_ui(
        {"created_entities": 2, "created_relations": 1, "entities_merged": 2}
    )
    assert summary["created_entities"] == 2
    assert summary["created_relations"] == 1
    print("OK ui_summary")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Knowledge graph harness smoke check")
    parser.parse_args()
    check_imports()
    check_rule_extract()
    check_mastery_math()
    check_ui_summary()
    print("\nHarness smoke: ALL PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
