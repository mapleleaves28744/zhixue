from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable
from uuid import UUID

import redis.asyncio as redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.schemas.profile import ProfileSummary

logger = logging.getLogger(__name__)


class ProfileContextCache:
    ttl_seconds = 1800

    def __init__(self, client_factory: Callable[[], object] | None = None) -> None:
        self.client_factory = client_factory or (
            lambda: redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=0.8,
            )
        )

    async def get_or_load(
        self,
        user_id: UUID,
        loader: Callable[[], Awaitable[ProfileSummary]],
    ) -> ProfileSummary:
        started = time.perf_counter()
        client = self.client_factory()
        try:
            cached = await client.get(self._key(user_id))
            if cached:
                logger.info("profile_context_cache hit user=%s duration_ms=%d", user_id, self._elapsed(started))
                return ProfileSummary.model_validate_json(cached)
            result = await loader()
            await client.set(self._key(user_id), result.model_dump_json(), ex=self.ttl_seconds)
            logger.info("profile_context_cache miss user=%s duration_ms=%d", user_id, self._elapsed(started))
            return result
        except (RedisError, OSError, ValueError, TypeError):
            logger.exception("profile_context_cache unavailable; falling back to database")
            return await loader()
        finally:
            await client.aclose()

    async def invalidate(self, user_id: UUID) -> None:
        client = self.client_factory()
        try:
            await client.delete(self._key(user_id))
        except (RedisError, OSError):
            logger.exception("profile_context_cache invalidation failed user=%s", user_id)
        finally:
            await client.aclose()

    @staticmethod
    def _key(user_id: UUID) -> str:
        return f"profile:context:{user_id}"

    @staticmethod
    def _elapsed(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)
