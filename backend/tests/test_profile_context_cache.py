from __future__ import annotations

from uuid import uuid4

import pytest

from app.schemas.profile import ProfileSummary
from app.services.profile_context_cache import ProfileContextCache


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.deleted: list[str] = []

    async def get(self, key: str):
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int):
        self.values[key] = value
        return True

    async def delete(self, key: str):
        self.deleted.append(key)
        self.values.pop(key, None)

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_profile_context_cache_reuses_summary_without_reloading() -> None:
    redis = FakeRedis()
    user_id = uuid4()
    calls = 0

    async def loader() -> ProfileSummary:
        nonlocal calls
        calls += 1
        return ProfileSummary(profile_summary="缓存画像", weak_points=["图"])

    cache = ProfileContextCache(client_factory=lambda: redis)
    first = await cache.get_or_load(user_id, loader)
    second = await cache.get_or_load(user_id, loader)

    assert first.profile_summary == second.profile_summary == "缓存画像"
    assert calls == 1


@pytest.mark.asyncio
async def test_profile_context_cache_invalidation_forces_reload() -> None:
    redis = FakeRedis()
    user_id = uuid4()
    calls = 0

    async def loader() -> ProfileSummary:
        nonlocal calls
        calls += 1
        return ProfileSummary(profile_summary=f"版本 {calls}")

    cache = ProfileContextCache(client_factory=lambda: redis)
    await cache.get_or_load(user_id, loader)
    await cache.invalidate(user_id)
    refreshed = await cache.get_or_load(user_id, loader)

    assert refreshed.profile_summary == "版本 2"
    assert calls == 2
