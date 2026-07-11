from __future__ import annotations

import importlib
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_hybrid_fusion_reranks_heading_keyword_and_source_quality() -> None:
    hybrid = importlib.import_module("app.rag.hybrid_retriever")

    weak_vector_only = hybrid.RetrievalCandidate(
        chunk_id=uuid4(),
        material_id=uuid4(),
        content="数组支持按下标随机访问，适合连续存储。",
        source_title="Array Lists",
        page_no=None,
        vector_score=0.82,
        keyword_score=0.0,
        vector_rank=1,
        keyword_rank=None,
        extra_meta={"chunk_type": "concept", "source_quality_score": 80},
    )
    strong_keyword_match = hybrid.RetrievalCandidate(
        chunk_id=uuid4(),
        material_id=uuid4(),
        content="哈希表冲突解决常用链地址法和开放定址法。",
        source_title="Hash Tables",
        page_no=None,
        vector_score=0.72,
        keyword_score=4.0,
        vector_rank=2,
        keyword_rank=1,
        extra_meta={
            "heading_path": ["查找", "哈希表", "冲突解决"],
            "chunk_type": "definition",
            "source_quality_score": 95,
        },
    )

    ranked = hybrid.fuse_and_rerank_results(
        "哈希表冲突解决是什么",
        [weak_vector_only, strong_keyword_match],
        top_k=2,
    )

    assert ranked[0].chunk_id == strong_keyword_match.chunk_id
    assert ranked[0].retrieval_mode == "hybrid"
    assert ranked[0].rerank_score > ranked[1].rerank_score


def test_hybrid_fusion_limits_single_source_dominance() -> None:
    hybrid = importlib.import_module("app.rag.hybrid_retriever")
    dominant = [
        hybrid.RetrievalCandidate(
            chunk_id=uuid4(),
            material_id=uuid4(),
            content=f"自有草稿片段 {index}：图的邻接矩阵和邻接表。",
            source_title="self",
            page_no=None,
            keyword_score=5.0,
            keyword_rank=index + 1,
            extra_meta={"source_id": "self-curated-draft", "chunk_type": "concept"},
        )
        for index in range(6)
    ]
    authority = hybrid.RetrievalCandidate(
        chunk_id=uuid4(),
        material_id=uuid4(),
        content="Open textbook explains adjacency lists and adjacency matrices.",
        source_title="Runestone",
        page_no=None,
        keyword_score=2.0,
        keyword_rank=7,
        extra_meta={"source_id": "runestone-pythonds", "chunk_type": "definition"},
    )

    ranked = hybrid.fuse_and_rerank_results("邻接矩阵和邻接表", [*dominant, authority], top_k=5)

    source_ids = [item.extra_meta.get("source_id") for item in ranked]
    assert "runestone-pythonds" in source_ids


def test_public_kb_index_migration_defines_keyword_and_metadata_indexes() -> None:
    migration_root = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    migration_files = list(migration_root.glob("*public_kb_hybrid_indexes.py"))

    assert migration_files, "missing public KB hybrid index migration"
    text = migration_files[0].read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in text
    assert "idx_document_chunks_extra_meta_gin" in text
    assert "idx_document_chunks_content_trgm" in text
    assert "idx_document_chunks_chapter_id_expr" in text
    assert "idx_document_chunks_source_id_expr" in text


def test_public_data_structure_course_payload_is_public_template() -> None:
    module = importlib.import_module("scripts.init_public_data_structure_kb")

    payload = module.public_course_payload()

    assert payload["title"] == "数据结构"
    assert payload["course_code"] == "DS-PUBLIC"
    assert payload["visibility"] == "public_template"
    assert payload["status"] == "active"


def test_public_kb_metrics_separate_retrieval_from_answer_quality() -> None:
    module = importlib.import_module("scripts.evaluate_public_kb")
    rows = [
        {
            "question": "栈是什么",
            "answerable": True,
            "expected_sources": ["runestone-pythonds"],
            "retrieved_source_ids": ["runestone-pythonds", "open-data-structures"],
            "llm_evaluated": True,
            "cited_source_ids": ["runestone-pythonds"],
            "answer_correct": True,
            "refused": False,
        },
        {
            "question": "B 树是什么",
            "answerable": True,
            "expected_sources": ["open-data-structures"],
            "retrieved_source_ids": [],
            "llm_evaluated": False,
            "cited_source_ids": [],
            "answer_correct": None,
            "refused": False,
        },
    ]

    metrics = module.calculate_metrics(rows)

    assert metrics["question_count"] == 2
    assert metrics["recall_at_5"] == 0.5
    assert metrics["mrr"] == 0.5
    assert metrics["citation_precision"] == 1.0
    assert metrics["answer_correctness"] == 1.0


def test_seed_material_metadata_is_json_safe() -> None:
    module = importlib.import_module("scripts.build_data_structure_kb")
    payload = {
        "source_id": "mit-ocw-6006",
        "imported_at": datetime(2026, 6, 6, tzinfo=UTC),
        "heading_path": ["图", "BFS"],
    }

    safe = module.json_safe_metadata(payload)

    assert safe == {
        "source_id": "mit-ocw-6006",
        "imported_at": "2026-06-06T00:00:00+00:00",
        "heading_path": ["图", "BFS"],
    }
