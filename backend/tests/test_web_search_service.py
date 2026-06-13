from __future__ import annotations

import pytest

from app.agent_runtime import supervisor_intents
from app.services.web_search_service import WebSearchService


def test_web_search_intent_detects_online_search_phrases() -> None:
    assert supervisor_intents.web_search_intent("联网搜索 Python 3.14 新特性")
    assert supervisor_intents.web_search_intent("帮我查一下网上最新的 AI 新闻")
    assert not supervisor_intents.web_search_intent("基于课程资料解释二叉树")
    assert not supervisor_intents.web_search_intent("检索课程知识库中的哈希表")


def test_plan_required_tools_prioritizes_search_web() -> None:
    tools = supervisor_intents.plan_required_tools("联网搜索 Rust 异步运行时对比", is_profile_update_only=False)
    assert tools[0] == "search_web"


def test_parse_markdown_results() -> None:
    service = WebSearchService(api_key="")
    raw = """## Search Results (2 results, 100ms)

### 1. Example Title
- **URL**: https://example.com/a
- This is a short summary about the topic.

### 2. Another Title
- **URL**: https://example.com/b
- Another summary line.
"""
    items = service._parse_markdown_results(raw)
    assert len(items) == 2
    assert items[0]["title"] == "Example Title"
    assert items[0]["url"] == "https://example.com/a"
    assert "summary" in items[0]["snippet"]


@pytest.mark.asyncio
async def test_search_returns_mock_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.web_search_service.settings.anysearch_enabled", True)
    monkeypatch.setattr("app.services.web_search_service.settings.anysearch_api_key", "")
    service = WebSearchService()
    payload = await service.search(query="测试联网搜索")
    assert payload["provider"] == "mock"
    assert payload["items"]


def test_supervisor_formats_search_web_answer_for_chat() -> None:
    from app.agent_runtime.supervisor import MiMoSupervisor

    supervisor = MiMoSupervisor(provider=object())  # type: ignore[arg-type]
    state = {
        "goal": "联网搜索 Python 3.14 有哪些新特性",
        "observations": [
            {
                "success": True,
                "tool_name": "search_web",
                "output": {
                    "query": "Python 3.14 新特性",
                    "provider": "anysearch",
                    "items": [
                        {
                            "title": "What’s new in Python 3.14",
                            "url": "https://docs.python.org/3/whatsnew/3.14.html",
                            "snippet": "This article explains the new features in Python 3.14.",
                        }
                    ],
                },
            }
        ],
    }
    answer = supervisor._build_completion_answer(state)
    assert "联网搜索" in answer
    assert "What’s new in Python 3.14" in answer
    assert "docs.python.org" in answer
    assert "所需学习内容已生成" not in answer
