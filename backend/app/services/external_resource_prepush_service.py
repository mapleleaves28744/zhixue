"""对话结束后后台预拉取主页外部学习资源。"""

from __future__ import annotations

import logging
from uuid import UUID

import redis.asyncio as redis
from arq.connections import RedisSettings, create_pool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

_GENERATING_TTL_SECONDS = 900


class ExternalResourcePrepushService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def schedule_from_recent_chat(self, *, user_id: UUID, course_id: UUID) -> None:
        user = await UserRepository(self.db).get_by_id(user_id)
        if user is None:
            return
        from app.services.external_resource_feed_service import ExternalResourceFeedService

        feed_service = ExternalResourceFeedService(self.db)
        topics, _ = await feed_service._resolve_topics(user, course_id)
        cache_key = feed_service._cache_key(user_id, course_id, topics)
        if await feed_service._load_cache(cache_key) is not None:
            return
        await self.enqueue(user_id=user_id, course_id=course_id, cache_key=cache_key)

    async def enqueue(self, *, user_id: UUID, course_id: UUID, cache_key: str) -> bool:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        try:
            claimed = await client.set(
                self._generating_key(cache_key),
                "1",
                nx=True,
                ex=_GENERATING_TTL_SECONDS,
            )
            if not claimed:
                return False
        finally:
            await client.aclose()

        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        try:
            job = await pool.enqueue_job(
                "run_prepush_external_feed_job",
                str(user_id),
                str(course_id),
                cache_key,
                _job_id=f"external-feed-prepush:{cache_key}",
            )
            return job is not None
        except Exception:
            logger.exception("external feed prepush enqueue failed")
            client = redis.from_url(settings.redis_url, decode_responses=True)
            try:
                await client.delete(self._generating_key(cache_key))
            finally:
                await client.aclose()
            return False
        finally:
            await pool.aclose()

    async def is_generating(self, cache_key: str) -> bool:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        try:
            return bool(await client.get(self._generating_key(cache_key)))
        finally:
            await client.aclose()

    async def clear_generating(self, cache_key: str) -> None:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        try:
            await client.delete(self._generating_key(cache_key))
        finally:
            await client.aclose()

    @staticmethod
    def _generating_key(cache_key: str) -> str:
        return f"{cache_key}:generating"


async def run_prepush_external_feed_job(
    ctx: dict,
    user_id: str,
    course_id: str,
    cache_key: str,
) -> dict:
    from app.db.session import AsyncSessionLocal
    from app.services.external_resource_feed_service import ExternalResourceFeedService

    prepush = ExternalResourcePrepushService(db=None)  # type: ignore[arg-type]
    async with AsyncSessionLocal() as db:
        user = await UserRepository(db).get_by_id(UUID(user_id))
        if user is None:
            await prepush.clear_generating(cache_key)
            return {"items": 0}
        try:
            payload = await ExternalResourceFeedService(db).generate_and_cache(
                current_user=user,
                course_id=UUID(course_id),
                expected_cache_key=cache_key,
            )
            return {"items": len(payload.get("items") or []), "cache_key": cache_key}
        except Exception:
            logger.exception("external feed prepush failed")
            return {"items": 0, "cache_key": cache_key}
        finally:
            await prepush.clear_generating(cache_key)
