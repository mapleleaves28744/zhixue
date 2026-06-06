from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

from app.rag.chunking import chunk_text

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_chunk_text_preserves_heading_metadata_and_source_fields() -> None:
    text = """# 栈与队列

## 栈

栈是一种只允许在一端进行插入和删除的线性结构。

```python
class Stack:
    def push(self, value):
        self.items.append(value)
```

## 队列

队列是一种先进先出的线性结构。
"""

    chunks = chunk_text(
        text,
        max_tokens=120,
        overlap=20,
        source_metadata={
            "source_id": "runestone-pythonds",
            "chapter_id": "ch03",
            "license": "CC BY-NC-SA 4.0",
            "source_quality_score": 93,
        },
    )

    assert chunks
    stack_chunk = next(chunk for chunk in chunks if "Stack" in chunk.content)
    assert stack_chunk.extra_meta["source_id"] == "runestone-pythonds"
    assert stack_chunk.extra_meta["chapter_id"] == "ch03"
    assert stack_chunk.extra_meta["license"] == "CC BY-NC-SA 4.0"
    assert stack_chunk.extra_meta["source_quality_score"] == 93
    assert stack_chunk.extra_meta["heading_path"] == ["栈与队列", "栈"]
    assert stack_chunk.extra_meta["chunk_type"] == "code"
    assert "```python\nclass Stack" in stack_chunk.content
    assert "def push" in stack_chunk.content


def test_discover_sources_marks_authoritative_importable_and_link_only_sources() -> None:
    discover = importlib.import_module("scripts.discover_course_sources")

    sources = discover.default_sources()
    by_id = {source["source_id"]: source for source in sources}

    assert by_id["open-data-structures"]["import_status"] == "approved_importable"
    assert by_id["open-data-structures"]["review_status"] == "approved"
    assert by_id["mit-ocw-6006"]["license"] == "CC BY-NC-SA 4.0"
    assert by_id["runestone-pythonds"]["risk_level"] == "medium"
    assert by_id["princeton-algs4"]["import_status"] == "approved_link_only"
    assert "license_url" in by_id["opendsa"]
    assert any(
        "_sources/BasicDS/WhatisaStack.rst" in item["url"]
        for item in by_id["runestone-pythonds"]["download_urls"]
    )
    assert any(
        "StackArray.html" in item["url"]
        for item in by_id["opendsa"]["download_urls"]
    )


def test_ingest_selects_only_approved_importable_sources() -> None:
    ingest = importlib.import_module("scripts.ingest_course_materials")
    sources = [
        {"source_id": "draft", "import_status": "candidate", "review_status": "unreviewed"},
        {"source_id": "link", "import_status": "approved_link_only", "review_status": "approved"},
        {"source_id": "importable", "import_status": "approved_importable", "review_status": "approved"},
        {"source_id": "needs-revision", "import_status": "approved_importable", "review_status": "needs_revision"},
    ]

    selected = ingest.select_importable_sources(sources)

    assert [source["source_id"] for source in selected] == ["importable"]


def test_ingest_clears_stale_download_failures(tmp_path: Path) -> None:
    ingest = importlib.import_module("scripts.ingest_course_materials")
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    failure_file = artifacts / "download_failures.json"
    failure_file.write_text('[{"source_id": "old", "error": "stale"}]', encoding="utf-8")

    ingest.record_download_failures(tmp_path, [])

    assert json.loads(failure_file.read_text(encoding="utf-8")) == []


def test_quality_report_counts_graphrag_ready_assets(tmp_path: Path) -> None:
    evaluate = importlib.import_module("scripts.evaluate_course_kb")
    source_root = tmp_path / "data_structure"
    (source_root / "normalized" / "self_curated").mkdir(parents=True)
    (source_root / "graph").mkdir()
    (source_root / "eval").mkdir()
    (source_root / "course_outline.yml").write_text(
        """
chapters:
  - chapter_id: ch01
    title: 绪论
  - chapter_id: ch02
    title: 线性表
""".strip(),
        encoding="utf-8",
    )
    (source_root / "normalized" / "self_curated" / "ch01.md").write_text(
        """
---
source_id: self-curated-draft
chapter_id: ch01
license: self-curated
---
# 绪论
""".strip(),
        encoding="utf-8",
    )
    (source_root / "graph" / "entities.yml").write_text(
        "entities:\n  - entity_id: kp_stack\n    entity_type: knowledge_point\n",
        encoding="utf-8",
    )
    (source_root / "graph" / "relations.yml").write_text(
        "relations:\n  - source_id: kp_stack\n    target_id: ch02\n    relation_type: belongs_to\n",
        encoding="utf-8",
    )
    (source_root / "graph" / "claims.yml").write_text(
        "claims:\n  - claim_id: c1\n    claim_type: definition\n    source_id: self-curated-draft\n",
        encoding="utf-8",
    )
    (source_root / "eval" / "standard_questions.yml").write_text(
        "questions:\n  - question: 栈是什么？\n    expected_sources: [self-curated-draft]\n",
        encoding="utf-8",
    )

    report = evaluate.evaluate_seed_knowledge(source_root)

    assert report["chapter_count"] == 2
    assert report["covered_chapter_count"] == 1
    assert report["source_traceability_rate"] == 1.0
    assert report["graph"]["entity_count"] == 1
    assert report["graph"]["relation_count"] == 1
    assert report["graph"]["claim_count"] == 1
    assert report["standard_question_count"] == 1
    stage_by_id = {stage["stage_id"]: stage for stage in report["pipeline_stages"]}
    assert list(stage_by_id) == [
        "raw_documents",
        "document_parsing",
        "cleaning_normalization",
        "hierarchy_chunking",
        "embedding",
        "indexing",
        "retrieval",
        "rerank",
        "llm_answer",
        "citations",
        "feedback_optimization",
    ]
    assert stage_by_id["document_parsing"]["status"] == "ready"
    assert stage_by_id["embedding"]["status"] == "ready_for_build"
    assert stage_by_id["indexing"]["status"] == "partial"
    assert stage_by_id["rerank"]["status"] == "planned"


def test_seed_quality_service_returns_report_and_source_risks(tmp_path: Path) -> None:
    service_module = importlib.import_module("app.services.seed_knowledge_service")
    source_root = tmp_path / "data_structure"
    (source_root / "eval").mkdir(parents=True)
    (source_root / "eval" / "quality_report.json").write_text(
        '{"graphrag_ready": true, "chapter_coverage_rate": 0.8, "graph": {"entity_count": 3}}',
        encoding="utf-8",
    )
    (source_root / "sources_manifest.yml").write_text(
        """
sources:
  - source_id: open-data-structures
    name: Open Data Structures
    import_status: approved_importable
    review_status: approved
    risk_level: low
    license: CC BY
  - source_id: princeton-algs4
    name: Princeton Algorithms
    import_status: approved_link_only
    review_status: approved
    risk_level: medium
    license: link-only
""".strip(),
        encoding="utf-8",
    )

    payload = service_module.load_seed_quality_report(source_root)

    assert payload["report"]["graphrag_ready"] is True
    assert payload["sources"][0]["source_id"] == "open-data-structures"
    assert payload["sources"][1]["import_status"] == "approved_link_only"


def test_seed_quality_service_preserves_pipeline_stage_statuses(tmp_path: Path) -> None:
    service_module = importlib.import_module("app.services.seed_knowledge_service")
    source_root = tmp_path / "data_structure"
    (source_root / "eval").mkdir(parents=True)
    (source_root / "eval" / "quality_report.json").write_text(
        """
{
  "pipeline_stages": [
    {"stage_id": "raw_documents", "status": "ready", "evidence": "raw files: 3"},
    {"stage_id": "rerank", "status": "planned", "evidence": "not implemented in Phase 1"}
  ]
}
""".strip(),
        encoding="utf-8",
    )
    (source_root / "sources_manifest.yml").write_text("sources: []", encoding="utf-8")

    payload = service_module.load_seed_quality_report(source_root)

    assert payload["report"]["pipeline_stages"][0]["stage_id"] == "raw_documents"
    assert payload["report"]["pipeline_stages"][1]["status"] == "planned"
