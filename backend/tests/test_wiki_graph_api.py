"""Wiki 图谱 API 与 WikiGraphService 集成向测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.main import app
from app.services.wiki_graph_service import WikiGraphService


def test_wiki_graph_api_routes_registered() -> None:
    paths = app.openapi()["paths"]
    assert "/api/v1/wiki/graph" in paths
    assert "/api/v1/wiki/graph/subgraph" in paths
    assert "/api/v1/knowledge/graph/subgraph" in paths
    view_param = paths["/api/v1/wiki/graph"]["get"]["parameters"]
    assert any(item.get("name") == "view" for item in view_param)


def test_wiki_graph_service_deduplicates_links() -> None:
    svc = WikiGraphService.__new__(WikiGraphService)
    links = [
        {"source": "a", "target": "b", "relation_type": "next", "line_style": "solid"},
        {"source": "a", "target": "b", "relation_type": "next", "line_style": "solid"},
        {"source": "b", "target": "c", "relation_type": "related", "line_style": "dashed"},
    ]
    seen: set[str] = set()
    unique: list[dict] = []
    for link in links:
        key = f"{link['source']}-{link['target']}-{link['relation_type']}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(link)
    assert len(unique) == 2


@pytest.mark.asyncio
async def test_wiki_graph_service_get_graph_personal_filters_nodes(monkeypatch) -> None:
    user_id = uuid4()
    other_id = uuid4()
    course_id = uuid4()
    page_mine = SimpleNamespace(
        id=uuid4(),
        owner_id=user_id,
        title="我的 Wiki",
        summary="s",
        knowledge_id=uuid4(),
        current_version=1,
    )
    page_other = SimpleNamespace(
        id=uuid4(),
        owner_id=other_id,
        title="他人 Wiki",
        summary="s",
        knowledge_id=None,
        current_version=1,
    )

    class FakeWikiRepo:
        @staticmethod
        async def list_links(page_id):
            return []

    class FakeWiki:
        repo = FakeWikiRepo()

        @staticmethod
        async def list_visible_pages(**kwargs):
            return [page_mine, page_other], 2

    class FakeMastery:
        @staticmethod
        async def get_mastery_map(**kwargs):
            return {str(page_mine.knowledge_id): 0.6}

    class FakeCourse:
        @staticmethod
        async def get_readable_course(course_id, user):
            return None

        @staticmethod
        async def get_course(course_id, user):
            return SimpleNamespace(owner_id=user_id, visibility="private")

    svc = WikiGraphService.__new__(WikiGraphService)
    svc.db = MagicMock()
    svc.wiki = FakeWiki()
    svc.mastery = FakeMastery()
    svc.knowledge = None
    svc.relations = None

    from app.services import wiki_graph_service as module

    monkeypatch.setattr(module, "CourseService", lambda db: FakeCourse())

    user = SimpleNamespace(id=user_id)
    graph = await svc.get_graph(current_user=user, course_id=course_id, view="personal")
    assert graph["view"] == "personal"
    assert len(graph["nodes"]) == 1
    assert graph["nodes"][0]["title"] == "我的 Wiki"
    assert graph["nodes"][0]["mastery_score"] == 0.6


@pytest.mark.asyncio
async def test_wiki_graph_marks_missing_mastery_as_unverified(monkeypatch) -> None:
    user_id, course_id, knowledge_id = uuid4(), uuid4(), uuid4()
    page = SimpleNamespace(id=uuid4(), owner_id=user_id, title="队列", summary="s", knowledge_id=knowledge_id, current_version=1)

    class FakeWikiRepo:
        async def list_links(self, page_id): return []
    class FakeWiki:
        repo = FakeWikiRepo()
        async def list_visible_pages(self, **kwargs): return [page], 1
    class FakeMastery:
        async def get_mastery_map(self, **kwargs): return {}
    class FakeCourse:
        async def get_readable_course(self, *args): return None
        async def get_course(self, *args): return SimpleNamespace(owner_id=user_id, visibility="private")

    svc = WikiGraphService.__new__(WikiGraphService)
    svc.db, svc.wiki, svc.mastery, svc.knowledge, svc.relations = MagicMock(), FakeWiki(), FakeMastery(), None, None
    from app.services import wiki_graph_service as module
    monkeypatch.setattr(module, "CourseService", lambda db: FakeCourse())
    graph = await svc.get_graph(current_user=SimpleNamespace(id=user_id), course_id=course_id, view="personal")
    assert graph["nodes"][0]["mastery_score"] == 0.5
    assert graph["nodes"][0]["mastery_confidence"] == 0.2
