"""外部学习资源推送 feed 测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.external_resource_feed_service import ExternalResourceFeedService


def test_normalize_item_rejects_mock_url() -> None:
    item = ExternalResourceFeedService.normalize_item(
        kind="blog",
        topic="Python",
        title="演示",
        url="https://example.com/mock-search",
        snippet="mock",
        reason="test",
    )
    assert item is None


def test_normalize_item_classifies_bilibili() -> None:
    item = ExternalResourceFeedService.normalize_item(
        kind="blog",
        topic="Python",
        title="Python 教程",
        url="https://www.bilibili.com/video/BV123",
        snippet="入门",
        reason="基于 Python 推荐",
    )
    assert item is not None
    assert item["kind"] == "video"
    assert item["topic"] == "Python"


def test_merge_topics_deduplicates_and_limits() -> None:
    topics = ExternalResourceFeedService.merge_topics(
        ["Python", "链表", "Python", "栈"],
        ["链表", "图", "队列", "哈希", "排序"],
        limit=5,
    )
    assert topics == ["Python", "链表", "栈", "图", "队列"]


def test_build_topics_reason_for_multiple() -> None:
    reason = ExternalResourceFeedService._build_topics_reason(["Python", "链表", "栈"])
    assert "Python" in reason
    assert "链表" in reason
    assert "栈" in reason


def test_dedupe_items_by_url() -> None:
    items = ExternalResourceFeedService.dedupe_items(
        [
            {"kind": "blog", "topic": "A", "title": "A", "url": "https://juejin.cn/post/1", "snippet": "", "source_domain": "", "reason": ""},
            {"kind": "blog", "topic": "A", "title": "A duplicate", "url": "https://juejin.cn/post/1?from=home", "snippet": "", "source_domain": "", "reason": ""},
            {"kind": "repo", "topic": "B", "title": "B", "url": "https://github.com/demo/repo", "snippet": "", "source_domain": "", "reason": ""},
        ]
    )
    assert len(items) == 2


@pytest.mark.asyncio
async def test_build_feed_uses_cache_when_not_refreshing() -> None:
    service = ExternalResourceFeedService(db=AsyncMock())
    user = MagicMock()
    user.id = uuid4()
    course_id = uuid4()
    cached_payload = {
        "primary_topic": "链表",
        "topics": ["链表", "栈"],
        "reason": "cached",
        "items": [
            {
                "kind": "blog",
                "topic": "链表",
                "title": "链表讲解",
                "url": "https://juejin.cn/post/linked-list",
                "snippet": "入门",
                "source_domain": "juejin.cn",
                "reason": "基于链表推荐",
            }
        ],
        "cached": False,
        "provider": "anysearch",
        "message": "",
    }

    with patch.object(service, "_resolve_topics", AsyncMock(return_value=(["链表", "栈"], "cached"))):
        with patch.object(service, "_load_cache", AsyncMock(return_value=cached_payload)):
            with patch("app.services.external_resource_feed_service.CourseService") as course_service:
                course_service.return_value.get_readable_course = AsyncMock()
                result = await service.build_feed(current_user=user, course_id=course_id, refresh=False)

    assert result["cached"] is True
    assert result["topics"] == ["链表", "栈"]


@pytest.mark.asyncio
async def test_build_feed_returns_generating_when_cache_miss() -> None:
    service = ExternalResourceFeedService(db=AsyncMock())
    user = MagicMock()
    user.id = uuid4()
    course_id = uuid4()
    search_service = MagicMock()
    search_service.enabled = True

    with patch(
        "app.services.external_resource_feed_service.WebSearchService",
        return_value=search_service,
    ), patch("app.services.external_resource_feed_service.CourseService") as course_service:
        course_service.return_value.get_readable_course = AsyncMock()
        with patch.object(
            service,
            "_resolve_topics",
            AsyncMock(return_value=(["二叉树", "链表"], "topic reason")),
        ):
            with patch.object(service, "_load_cache", AsyncMock(return_value=None)):
                with patch(
                    "app.services.external_resource_prepush_service.ExternalResourcePrepushService"
                ) as prepush_cls:
                    prepush = prepush_cls.return_value
                    prepush.is_generating = AsyncMock(return_value=False)
                    prepush.enqueue = AsyncMock(return_value=True)
                    result = await service.build_feed(current_user=user, course_id=course_id, refresh=False)

    assert result["prepush_status"] == "generating"
    assert result["items"] == []
    prepush.enqueue.assert_awaited_once()


@pytest.mark.asyncio
async def test_build_feed_aggregates_parallel_search_results() -> None:
    service = ExternalResourceFeedService(db=AsyncMock())
    user = MagicMock()
    user.id = uuid4()
    course_id = uuid4()

    async def fake_search(*, query: str, max_results: int, domain: str | None = None):
        if domain == "bilibili.com":
            return {
                "items": [
                    {"title": "B站视频", "url": "https://www.bilibili.com/video/BV1", "snippet": "video"},
                ]
            }
        if domain == "github.com":
            return {
                "items": [
                    {"title": "GitHub 仓库", "url": "https://github.com/demo/awesome-ds", "snippet": "repo"},
                ]
            }
        return {
            "items": [
                {"title": "技术博客", "url": "https://juejin.cn/post/ds", "snippet": "blog"},
            ]
        }

    search_service = MagicMock()
    search_service.enabled = True
    search_service.search = AsyncMock(side_effect=fake_search)

    with patch("app.services.external_resource_feed_service.CourseService") as course_service:
        course_service.return_value.get_readable_course = AsyncMock()
        with patch.object(
            service,
            "_resolve_topics",
            AsyncMock(return_value=(["二叉树", "链表"], "topic reason")),
        ):
            with patch.object(service, "_load_cache", AsyncMock(return_value=None)):
                with patch.object(service, "_save_cache", AsyncMock()):
                    with patch("app.services.external_resource_feed_service.WebSearchService", return_value=search_service):
                        result = await service.build_feed(current_user=user, course_id=course_id, refresh=True)

    kinds = {item["kind"] for item in result["items"]}
    assert kinds == {"video", "blog", "repo"}
    assert len(result["topics"]) == 2
