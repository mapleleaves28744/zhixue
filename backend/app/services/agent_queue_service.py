from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import redis.asyncio as redis
from arq.connections import RedisSettings, create_pool
from redis.exceptions import RedisError, ResponseError

from app.core.config import settings


logger = logging.getLogger(__name__)


class AgentEventBroker:
    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url or settings.redis_url

    async def publish(self, task_id: UUID, event_type: str, payload: dict[str, Any]) -> None:
        client = redis.from_url(self.redis_url, decode_responses=True)
        serialized = json.dumps(
            {"event_type": event_type, "payload": payload},
            ensure_ascii=False,
        )
        try:
            try:
                await client.xadd(
                    self._key(task_id),
                    {"event_type": event_type, "payload": json.dumps(payload, ensure_ascii=False)},
                    maxlen=1000,
                    approximate=True,
                )
                await client.expire(self._key(task_id), 86400)
            except ResponseError as exc:
                if "XADD" not in str(exc).upper():
                    raise
                await client.publish(self._pubsub_key(task_id), serialized)
        except RedisError:
            logger.exception("Agent event broker publish failed; database event remains authoritative")
        finally:
            await client.aclose()

    async def stream(self, task_id: UUID, last_id: str = "$") -> AsyncIterator[dict[str, Any]]:
        client = redis.from_url(self.redis_url, decode_responses=True)
        cursor = last_id
        try:
            while True:
                try:
                    batches = await client.xread({self._key(task_id): cursor}, block=15000, count=50)
                except ResponseError as exc:
                    if "XREAD" not in str(exc).upper():
                        raise
                    async for event in self._stream_pubsub(client, task_id):
                        yield event
                    return
                if not batches:
                    yield {"event_type": "heartbeat", "payload": {}}
                    continue
                for _, items in batches:
                    for item_id, fields in items:
                        cursor = item_id
                        event_type = str(fields.get("event_type") or "message")
                        try:
                            payload = json.loads(fields.get("payload") or "{}")
                        except json.JSONDecodeError:
                            payload = {}
                        yield {"event_type": event_type, "payload": payload, "redis_id": item_id}
                        if event_type in {"completed", "failed", "cancelled"}:
                            return
        finally:
            await client.aclose()

    def _key(self, task_id: UUID) -> str:
        return f"agent:task:{task_id}:events"

    def _pubsub_key(self, task_id: UUID) -> str:
        return f"agent:task:{task_id}:pubsub"

    async def _stream_pubsub(self, client, task_id: UUID) -> AsyncIterator[dict[str, Any]]:
        pubsub = client.pubsub()
        await pubsub.subscribe(self._pubsub_key(task_id))
        try:
            while True:
                item = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15)
                if item is None:
                    yield {"event_type": "heartbeat", "payload": {}}
                    continue
                try:
                    data = json.loads(item.get("data") or "{}")
                except (json.JSONDecodeError, TypeError):
                    data = {}
                event_type = str(data.get("event_type") or "message")
                yield {"event_type": event_type, "payload": data.get("payload") or {}}
                if event_type in {"completed", "failed", "cancelled"}:
                    return
        finally:
            await pubsub.unsubscribe(self._pubsub_key(task_id))
            await pubsub.aclose()


class AgentQueueService:
    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url or settings.redis_url

    async def enqueue(self, task_id: UUID, *, approved: bool | None = None) -> bool:
        pool = await create_pool(RedisSettings.from_dsn(self.redis_url))
        try:
            function = "resume_agent_task_job" if approved is not None else "run_agent_task_job"
            args: tuple[object, ...] = (str(task_id), approved) if approved is not None else (str(task_id),)
            job = await pool.enqueue_job(
                function,
                *args,
                _job_id=f"agent:{task_id}:{'resume' if approved is not None else 'run'}",
            )
            return job is not None
        finally:
            await pool.aclose()
