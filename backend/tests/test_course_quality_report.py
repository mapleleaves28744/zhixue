from __future__ import annotations

from app.services.seed_knowledge_service import build_runtime_course_report


def test_runtime_course_quality_report_uses_course_counts_not_seed_file() -> None:
    report = build_runtime_course_report(
        course_id="course-1",
        metrics={
            "material_count": 4,
            "parsed_material_count": 4,
            "chunk_count": 210,
            "knowledge_point_count": 50,
            "wiki_page_count": 50,
            "sourced_wiki_page_count": 30,
            "qualified_wiki_page_count": 24,
            "wiki_source_count": 92,
            "wiki_link_count": 229,
        },
    )

    assert report["report_scope"] == "course_runtime"
    assert report["raw_document_count"] == 4
    assert report["chunk_count"] == 210
    assert report["wiki"]["page_count"] == 50
    assert report["wiki"]["source_coverage_rate"] == 0.6
    assert report["graphrag_ready"] is True

