from __future__ import annotations

from types import SimpleNamespace

from app.services.wiki_service import describe_wiki_page_quality


def test_wiki_quality_marks_short_unsourced_page_for_enrichment() -> None:
    page = SimpleNamespace(content="关于哈希表的个性化讲解资料", sources=[])

    quality = describe_wiki_page_quality(page)

    assert quality["status"] == "needs_enrichment"
    assert quality["source_count"] == 0
    assert quality["content_length"] < 300


def test_wiki_quality_marks_structured_sourced_page_as_verified() -> None:
    page = SimpleNamespace(
        content="# 队列\n\n## 定义\n" + "队列遵循先进先出。" * 60 + "\n\n## 易错点\n队首和队尾的方向不能混淆。",
        sources=[SimpleNamespace(id="source-1")],
    )

    quality = describe_wiki_page_quality(page)

    assert quality["status"] == "verified"
    assert quality["source_count"] == 1
    assert quality["section_count"] >= 2

