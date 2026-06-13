"""对话结束后预生成练习，进入练习页即可直接刷题。"""

from __future__ import annotations

import logging
from uuid import UUID

import redis.asyncio as redis
from arq.connections import RedisSettings, create_pool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.user_repository import UserRepository
from app.schemas.quiz import QuizGenerateRequest
from app.services.practice_suggestion_service import PracticeSuggestionService
from app.services.quiz_service import QuizService

logger = logging.getLogger(__name__)

_PREPUSH_TTL_SECONDS = 86400


class PracticePrepushService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def schedule_from_recent_chat(self, *, user_id: UUID, course_id: UUID) -> None:
        user = await UserRepository(self.db).get_by_id(user_id)
        if user is None:
            return
        await PracticeSuggestionService(self.db).suggest(
            current_user=user,
            course_id=course_id,
            trigger_prepush=True,
        )

    async def enqueue(self, *, user_id: UUID, course_id: UUID, topic: str) -> bool:
        key = self._redis_key(user_id, course_id, topic)
        client = redis.from_url(settings.redis_url, decode_responses=True)
        try:
            claimed = await client.set(key, "generating", nx=True, ex=900)
            if not claimed:
                current = await client.get(key)
                return current not in {None, "generating"}
        finally:
            await client.aclose()

        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        try:
            job = await pool.enqueue_job(
                "run_prepush_practice_quiz_job",
                str(user_id),
                str(course_id),
                topic,
                _job_id=f"practice-prepush:{user_id}:{course_id}:{topic}",
            )
            return job is not None
        except Exception:
            logger.exception("practice prepush enqueue failed")
            client = redis.from_url(settings.redis_url, decode_responses=True)
            try:
                await client.delete(key)
            finally:
                await client.aclose()
            return False
        finally:
            await pool.aclose()

    async def get_cached_quiz_id(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        topic: str,
    ) -> UUID | None:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        try:
            value = await client.get(self._redis_key(user_id, course_id, topic))
            if value and value not in {"generating", "failed"}:
                return UUID(value)
        except (ValueError, TypeError):
            return None
        finally:
            await client.aclose()
        return None

    async def get_prepush_status(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        topic: str,
        existing_quiz_id: UUID | None,
    ) -> str:
        if existing_quiz_id is not None:
            return "ready"
        client = redis.from_url(settings.redis_url, decode_responses=True)
        try:
            value = await client.get(self._redis_key(user_id, course_id, topic))
            if value == "generating":
                return "generating"
            if value and value not in {"generating", "failed"}:
                return "ready"
        finally:
            await client.aclose()
        return "none"

    async def generate_now(self, *, user_id: UUID, course_id: UUID, topic: str) -> UUID | None:
        user = await UserRepository(self.db).get_by_id(user_id)
        if user is None:
            return None

        suggestion_service = PracticeSuggestionService(self.db)
        existing = await suggestion_service._find_recent_quiz_for_topic(
            user_id=user_id,
            course_id=course_id,
            topic=topic,
        )
        if existing:
            await self._mark_ready(user_id, course_id, topic, existing)
            return existing

        cached = await self.get_cached_quiz_id(
            user_id=user_id,
            course_id=course_id,
            topic=topic,
        )
        if cached:
            return cached

        key = self._redis_key(user_id, course_id, topic)
        client = redis.from_url(settings.redis_url, decode_responses=True)
        try:
            await client.set(key, "generating", ex=900)
        finally:
            await client.aclose()

        try:
            result = await QuizService(self.db).generate_quiz(
                payload=QuizGenerateRequest(
                    course_id=course_id,
                    topic=topic,
                    quiz_type="practice",
                    question_types=["single_choice"],
                    count=5,
                    difficulty="medium",
                ),
                current_user=user,
            )
            await self._mark_ready(user_id, course_id, topic, result.quiz_id)
            return result.quiz_id
        except Exception:
            logger.exception("practice prepush generate failed")
            client = redis.from_url(settings.redis_url, decode_responses=True)
            try:
                await client.set(key, "failed", ex=300)
            finally:
                await client.aclose()
            return None

    async def _mark_ready(self, user_id: UUID, course_id: UUID, topic: str, quiz_id: UUID) -> None:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        try:
            await client.set(
                self._redis_key(user_id, course_id, topic),
                str(quiz_id),
                ex=_PREPUSH_TTL_SECONDS,
            )
        finally:
            await client.aclose()

    @staticmethod
    def _redis_key(user_id: UUID, course_id: UUID, topic: str) -> str:
        safe_topic = topic.replace(" ", "_")[:48]
        return f"practice:prepush:{user_id}:{course_id}:{safe_topic}"


async def run_prepush_practice_quiz_job(ctx: dict, user_id: str, course_id: str, topic: str) -> dict:
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        service = PracticePrepushService(db)
        quiz_id = await service.generate_now(
            user_id=UUID(user_id),
            course_id=UUID(course_id),
            topic=topic,
        )
        return {"quiz_id": str(quiz_id) if quiz_id else None, "topic": topic}
