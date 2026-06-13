"""练习推荐：基于最近 AI 助手提问提取知识点。"""

from __future__ import annotations

from app.services.practice_suggestion_service import PracticeSuggestionService


def test_extract_topics_from_question_text() -> None:
    service = PracticeSuggestionService(db=None)  # type: ignore[arg-type]
    topics = service._extract_topics(
        [
            "生成5道关于链表的练习题",
            "解释一下二叉树的中序遍历",
        ]
    )
    assert "链表" in topics
    assert "二叉树" in topics or "中序遍历" in topics


def test_topics_from_text_about_pattern() -> None:
    service = PracticeSuggestionService(db=None)  # type: ignore[arg-type]
    topics = service._topics_from_text("生成一份关于哈希表的讲解资料")
    assert "哈希表" in topics


def test_topics_from_text_prefers_recent_web_search_topic() -> None:
    service = PracticeSuggestionService(db=None)  # type: ignore[arg-type]
    topics = service._extract_topics(
        [
            "联网搜索 Python 3.14 有哪些新特性",
            "生成二叉树ppt和队列思维导图",
        ]
    )
    assert topics[0] == "Python 3.14"


def test_normalize_topic_uses_version_from_source_question() -> None:
    service = PracticeSuggestionService(db=None)  # type: ignore[arg-type]
    topic = service._normalize_topic_label("Python", "联网搜索 Python 3.14 有哪些新特性")
    assert topic == "Python 3.14"


def test_build_reason_is_concise() -> None:
    service = PracticeSuggestionService(db=None)  # type: ignore[arg-type]
    reason = service._build_reason(["联网搜索 Python 3.14 有哪些新特性"], "Python 3.14")
    assert "12 条" not in reason
    assert "例如" not in reason
    assert "Python 3.14" in reason
