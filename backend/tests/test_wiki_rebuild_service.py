from __future__ import annotations

from types import SimpleNamespace

from app.services.wiki_generate_service import WikiGenerateService


def test_rebuild_template_is_structured_and_keeps_course_evidence() -> None:
    chunks = [
        SimpleNamespace(
            source_title="03_栈与队列.md",
            content="队列是一种先进先出的线性表，入队在队尾进行，出队在队首进行。",
        )
    ]

    content = WikiGenerateService._rebuild_template_content(
        "队列",
        "受限的线性表结构。",
        chunks,
    )

    assert "## 定义" in content
    assert "## 核心内容" in content
    assert "## 来源说明" in content
    assert "先进先出" in content


def test_rebuild_source_selection_prefers_matching_material_chunks() -> None:
    chunks = [
        SimpleNamespace(content="链表通过指针连接结点。"),
        SimpleNamespace(content="队列的入队操作在队尾进行。"),
        SimpleNamespace(content="栈的出栈操作删除栈顶元素。"),
    ]

    selected = WikiGenerateService._select_rebuild_source_chunks("队列", chunks)

    assert selected[0] is chunks[1]


def test_rebuild_uses_version_history_when_page_version_is_stale() -> None:
    versions = [SimpleNamespace(version_number=1), SimpleNamespace(version_number=2)]

    next_version = WikiGenerateService._next_rebuild_version(1, versions)

    assert next_version == 3
