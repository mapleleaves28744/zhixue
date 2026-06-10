#!/usr/bin/env python3
"""Lightweight harness: multimodal review + supervisor routing smoke (no live LLM/worker)."""

from __future__ import annotations

import asyncio
import sys
from uuid import uuid4

from app.agent_runtime.supervisor import MiMoSupervisor
from app.llm.schemas import ChatResponse
from app.services.multimodal_review_service import MultimodalReviewService
from types import SimpleNamespace


class _CompleteWithoutTools:
    async def chat(self, messages, **kwargs):
        return ChatResponse(content='{"status":"complete","final_answer":"done"}')


async def main() -> int:
    asset_id = uuid4()
    user_id = uuid4()
    asset = SimpleNamespace(
        id=asset_id,
        user_id=user_id,
        asset_type="image",
        title="测试插图",
        description="",
        prompt="BFS 概念图",
        mime_type="image/png",
        citations=[{"title": "BFS", "quote": "队列"}],
        render_meta={},
    )

    class _FakeDb:
        async def commit(self) -> None:
            return None

        async def refresh(self, obj: object) -> None:
            return None

    class _Repo:
        async def get_asset_for_user(self, aid, uid):
            return asset if aid == asset_id and uid == user_id else None

        async def update_asset(self, a, **values):
            return a

    review_service = MultimodalReviewService(_FakeDb())  # type: ignore[arg-type]
    review_service.media = _Repo()  # type: ignore[assignment]
    review = await review_service.review_asset(asset_id, user_id)
    if not review.get("passed"):
        print("[FAIL] expected grounded asset to pass review", review)
        return 1

    decision = await MiMoSupervisor(provider=_CompleteWithoutTools()).decide(
        {
            "goal": f"请审核多模态产物 {asset_id} 的安全与引用",
            "messages": [],
            "observations": [],
            "tool_call_count": 0,
        },
        [
            {
                "type": "function",
                "function": {
                    "name": "review_multimodal_asset",
                    "description": "审核",
                    "parameters": {
                        "type": "object",
                        "properties": {"asset_id": {"type": "string"}},
                        "required": ["asset_id"],
                    },
                },
            }
        ],
    )
    if decision.status != "continue" or decision.tool_calls[0].name != "review_multimodal_asset":
        print("[FAIL] supervisor did not route review_multimodal_asset", decision)
        return 1

    print("[OK] multimodal harness passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
