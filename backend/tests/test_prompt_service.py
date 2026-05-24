from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.core.exceptions import BusinessException
from app.llm.prompt_renderer import PromptRenderer
from app.models.prompt import PromptVersion
from app.services.prompt_service import PromptService


class FakeResult:
    def __init__(self, value: object | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object | None:
        return self.value


class FakeDB:
    def __init__(self, value: object | None = None) -> None:
        self.value = value

    async def execute(self, statement: object) -> FakeResult:
        return FakeResult(self.value)


def test_prompt_service_uses_default_template_when_database_missing() -> None:
    asyncio.run(_test_prompt_service_uses_default_template_when_database_missing())


async def _test_prompt_service_uses_default_template_when_database_missing() -> None:
    service = PromptService(FakeDB())  # type: ignore[arg-type]

    rendered = await service.render_prompt(
        agent_name="WikiAgent",
        scene="wiki.generate",
        params={
            "knowledge_name": "栈与队列",
            "knowledge_description": "受限线性表",
            "chunk_text": "栈是后进先出，队列是先进先出。",
        },
    )

    assert rendered.source == "default"
    assert "栈与队列" in rendered.content
    assert "栈是后进先出" in rendered.content


def test_prompt_service_uses_active_database_template() -> None:
    asyncio.run(_test_prompt_service_uses_active_database_template())


async def _test_prompt_service_uses_active_database_template() -> None:
    version = PromptVersion(
        id=uuid4(),
        agent_name="WikiAgent",
        scene="wiki.generate",
        version_no=2,
        template_content="数据库模板：{knowledge_name}",
        parameters_schema={},
        status="active",
        created_by="system",
    )
    service = PromptService(FakeDB(version))  # type: ignore[arg-type]

    rendered = await service.render_prompt(
        agent_name="WikiAgent",
        scene="wiki.generate",
        params={"knowledge_name": "图"},
    )

    assert rendered.source == "database"
    assert rendered.prompt_version_id == version.id
    assert rendered.content == "数据库模板：图"


def test_prompt_renderer_reports_missing_variables() -> None:
    renderer = PromptRenderer()

    with pytest.raises(BusinessException):
        renderer.render("请解释 {topic} 和 {missing}", {"topic": "排序"})
