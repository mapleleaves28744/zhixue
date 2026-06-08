from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agent_runtime.service_tools import build_learning_tool_registry
from app.agent_runtime.tools import ToolContext
from app.services.multimodal_review_service import MultimodalReviewService


class _FakeMediaRepo:
    def __init__(self, asset: SimpleNamespace) -> None:
        self.asset = asset
        self.updated: dict[str, object] | None = None

    async def get_asset_for_user(self, asset_id, user_id):
        if self.asset.id == asset_id and self.asset.user_id == user_id:
            return self.asset
        return None

    async def update_asset(self, asset, **values):
        for key, value in values.items():
            setattr(asset, key, value)
        self.updated = values
        return asset


class _FakeDb:
    async def commit(self) -> None:
        return None

    async def refresh(self, obj: object) -> None:
        return None


@pytest.mark.asyncio
async def test_multimodal_review_flags_missing_citations() -> None:
    user_id = uuid4()
    asset_id = uuid4()
    asset = SimpleNamespace(
        id=asset_id,
        user_id=user_id,
        asset_type="image",
        title="BFS 插图",
        description="",
        prompt="教学概念图",
        mime_type="image/png",
        citations=[],
        render_meta={},
    )
    service = MultimodalReviewService(_FakeDb())  # type: ignore[arg-type]
    service.media = _FakeMediaRepo(asset)  # type: ignore[assignment]

    result = await service.review_asset(asset_id, user_id)

    assert result["passed"] is False
    assert result["risk_level"] == "medium"
    assert any("缺少课程资料引用" in item for item in result["issues"])
    assert service.media.updated is not None


@pytest.mark.asyncio
async def test_multimodal_review_passes_grounded_courseware() -> None:
    user_id = uuid4()
    asset_id = uuid4()
    asset = SimpleNamespace(
        id=asset_id,
        user_id=user_id,
        asset_type="courseware",
        title="BFS 课件",
        description="",
        prompt="",
        mime_type="text/html",
        citations=[{"title": "BFS", "quote": "队列实现"}],
        render_meta={
            "spec": {
                "title": "BFS",
                "steps": [{"title": "步骤1", "body": "入队根节点", "hint": "注意 visited"}],
            }
        },
    )
    service = MultimodalReviewService(_FakeDb())  # type: ignore[arg-type]
    service.media = _FakeMediaRepo(asset)  # type: ignore[assignment]

    result = await service.review_asset(asset_id, user_id)

    assert result["passed"] is True
    assert result["risk_level"] == "low"


def test_review_multimodal_asset_tool_is_registered() -> None:
    registry = build_learning_tool_registry(
        SimpleNamespace(),
        SimpleNamespace(id=uuid4(), role="student"),
    )
    names = {item["function"]["name"] for item in registry.tool_schemas()}
    assert "review_multimodal_asset" in names


@pytest.mark.asyncio
async def test_supervisor_routes_multimodal_review_goal() -> None:
    from app.agent_runtime.supervisor import MiMoSupervisor
    from app.llm.schemas import ChatResponse

    class DirectCompleteProvider:
        async def chat(self, messages, **kwargs):
            return ChatResponse(content='{"status":"complete","final_answer":"已审核"}')

    tools = [
        {
            "type": "function",
            "function": {
                "name": "review_multimodal_asset",
                "description": "审核多模态",
                "parameters": {
                    "type": "object",
                    "properties": {"asset_id": {"type": "string"}},
                    "required": ["asset_id"],
                },
            },
        }
    ]
    asset_id = str(uuid4())
    decision = await MiMoSupervisor(provider=DirectCompleteProvider()).decide(
        {
            "goal": f"请审核多模态产物 {asset_id} 的安全与引用依据",
            "messages": [],
            "observations": [],
            "tool_call_count": 0,
        },
        tools,
    )
    assert decision.status == "continue"
    assert decision.tool_calls[0].name == "review_multimodal_asset"
    assert decision.tool_calls[0].arguments["asset_id"] == asset_id
