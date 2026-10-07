from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learning_record import LearningRecord
from app.models.memory import MemoryReflectionJob
from app.models.user import User
from app.services.conversation_intent import is_simple_greeting
from app.services.memory_service import MemoryService
from app.services.memory_suppression_service import MemorySuppressionService


ELIGIBLE_EVENTS = {"chat", "quiz_submit", "diagnosis_generated", "feedback"}
EXTRACTOR_VERSION = "v1"


class MemoryReflectionService:
    """Durable discovery, leasing and fenced application of memory candidates."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def discover_missing(
        self, *, user_id: UUID | None = None, course_id: UUID | None = None,
        all_scopes: bool = False, limit: int = 200,
    ) -> int:
        existing = select(MemoryReflectionJob.source_record_id).where(
            MemoryReflectionJob.source_record_id == LearningRecord.id,
            MemoryReflectionJob.extractor_version == EXTRACTOR_VERSION,
        ).exists()
        statement = select(LearningRecord).where(
            LearningRecord.event_type.in_(ELIGIBLE_EVENTS), ~existing,
        )
        if user_id is not None:
            statement = statement.where(LearningRecord.user_id == user_id)
        if not all_scopes:
            statement = statement.where(
                LearningRecord.course_id == course_id if course_id else LearningRecord.course_id.is_(None)
            )
        records = list((await self.db.execute(
            statement.order_by(LearningRecord.created_at.asc(), LearningRecord.id.asc()).limit(limit)
        )).scalars().all())
        created = 0
        suppressed_by_scope: dict[tuple[UUID, UUID | None], set[str]] = {}
        for record in records:
            scope = (record.user_id, record.course_id)
            if scope not in suppressed_by_scope:
                suppressed_by_scope[scope] = await MemorySuppressionService(self.db).source_record_ids(
                    user_id=record.user_id, course_id=record.course_id,
                )
            forgotten_source = str(record.id) in suppressed_by_scope[scope]
            greeting = record.event_type == "chat" and is_simple_greeting(str((record.event_payload or {}).get("question") or ""))
            result = await self.db.execute(pg_insert(MemoryReflectionJob).values(
                user_id=record.user_id, course_id=record.course_id,
                source_record_id=record.id, extractor_version=EXTRACTOR_VERSION,
                status="skipped" if greeting or forgotten_source else "pending",
                candidate_payload={"reason": "forgotten_source" if forgotten_source else "greeting"} if greeting or forgotten_source else {},
            ).on_conflict_do_nothing(constraint="uq_memory_reflection_jobs_source_version"))
            created += int(result.rowcount or 0)
        await self.db.commit()
        return created

    async def process_next_batch(
        self, *, user_id: UUID | None = None, course_id: UUID | None = None,
        all_scopes: bool = False, include_recent: bool = False,
    ) -> dict[str, int]:
        now = datetime.now(UTC)
        available = or_(
            MemoryReflectionJob.status == "pending",
            MemoryReflectionJob.status == "retry",
            (MemoryReflectionJob.status == "running") & (MemoryReflectionJob.lease_until < now),
        )
        statement = select(MemoryReflectionJob).where(
            available,
            or_(MemoryReflectionJob.retry_at.is_(None), MemoryReflectionJob.retry_at <= now),
        )
        if user_id is not None:
            statement = statement.where(MemoryReflectionJob.user_id == user_id)
        if not all_scopes:
            statement = statement.where(
                MemoryReflectionJob.course_id == course_id if course_id else MemoryReflectionJob.course_id.is_(None)
            )
        if not include_recent:
            statement = statement.where(MemoryReflectionJob.created_at < now - timedelta(minutes=2))
        first = (await self.db.execute(
            statement.order_by(MemoryReflectionJob.created_at.asc()).limit(1).with_for_update(skip_locked=True).execution_options(populate_existing=True)
        )).scalar_one_or_none()
        if first is None:
            return {"jobs": 0, "created": 0, "reinforced": 0}
        scope = [MemoryReflectionJob.user_id == first.user_id]
        scope.append(MemoryReflectionJob.course_id == first.course_id if first.course_id else MemoryReflectionJob.course_id.is_(None))
        jobs = list((await self.db.execute(
            statement.where(*scope).order_by(MemoryReflectionJob.created_at.asc()).limit(30).with_for_update(skip_locked=True).execution_options(populate_existing=True)
        )).scalars().all())
        owner = uuid4().hex
        versions = {}
        for job in jobs:
            job.status = "running"
            job.lease_owner = owner
            job.lease_until = now + timedelta(minutes=5)
            job.lease_version += 1
            job.attempts += 1
            versions[job.id] = job.lease_version
        record_ids = [job.source_record_id for job in jobs]
        await self.db.commit()

        try:
            records = list((await self.db.execute(select(LearningRecord).where(
                LearningRecord.id.in_(record_ids), LearningRecord.user_id == first.user_id,
            ).order_by(LearningRecord.created_at.asc(), LearningRecord.id.asc()))).scalars().all())
            suppressed = await MemorySuppressionService(self.db).source_record_ids(
                user_id=first.user_id, course_id=first.course_id,
            )
            records = [record for record in records if str(record.id) not in suppressed]
            from app.agents.memory_agent import MemoryAgent

            candidates = await MemoryAgent(self.db).extract_candidates(first.user_id, records) if records else []
            locked = list((await self.db.execute(select(MemoryReflectionJob).where(
                MemoryReflectionJob.id.in_(versions),
            ).with_for_update().execution_options(populate_existing=True))).scalars().all())
            if len(locked) != len(versions) or any(
                job.status != "running" or job.lease_owner != owner
                or job.lease_version != versions[job.id] for job in locked
            ):
                await self.db.rollback()
                return {"jobs": 0, "created": 0, "reinforced": 0}
            # Serialize with user initiated forget before applying extracted facts.
            await self.db.execute(select(User.id).where(User.id == first.user_id).with_for_update())
            suppressed = await MemorySuppressionService(self.db).source_record_ids(
                user_id=first.user_id, course_id=first.course_id,
            )
            source_ids = {str(record.id) for record in records}
            created = reinforced = pending = 0
            for candidate in candidates:
                evidence = [
                    item for item in MemoryService.normalize_evidence(candidate.get("evidence"))
                    if str(item) in source_ids and str(item) not in suppressed
                ]
                content = str(candidate.get("content") or "").strip()
                if not evidence or not content or candidate.get("suggested_action") == "ignore":
                    continue
                related_id = candidate.get("related_memory_id")
                _, action = await MemoryService(self.db).upsert_memory(
                    user_id=first.user_id, course_id=first.course_id,
                    memory_type=str(candidate.get("memory_type") or "insight"),
                    content=content, evidence=evidence,
                    confidence=float(candidate.get("confidence") or 0.8),
                    suggested_action=str(candidate.get("suggested_action") or "add"),
                    related_memory_id=UUID(str(related_id)) if related_id else None,
                )
                created += action == "add"
                reinforced += action == "reinforce"
                pending += action == "pending"
            for job in locked:
                job.status = "succeeded" if created or reinforced or pending else "succeeded_no_output"
                job.candidate_payload = {"batch_candidate_count": len(candidates), "created": created, "reinforced": reinforced, "pending_review": pending}
                job.lease_owner = None
                job.lease_until = None
                job.retry_at = None
                job.updated_at = datetime.now(UTC)
            await self.db.commit()
            return {"jobs": len(jobs), "created": created, "reinforced": reinforced}
        except Exception as exc:
            await self.db.rollback()
            failed = list((await self.db.execute(select(MemoryReflectionJob).where(
                MemoryReflectionJob.id.in_(versions),
            ).with_for_update().execution_options(populate_existing=True))).scalars().all())
            for job in failed:
                if job.lease_owner != owner or job.lease_version != versions.get(job.id):
                    continue
                job.status = "failed" if job.attempts >= 5 else "retry"
                job.retry_at = datetime.now(UTC) + timedelta(seconds=min(30 * 2 ** job.attempts, 3600))
                job.last_error = str(exc)[:1000]
                job.lease_owner = None
                job.lease_until = None
            await self.db.commit()
            raise

    async def reflect_scope(self, *, user_id: UUID, course_id: UUID | None) -> dict[str, int]:
        await self.discover_missing(user_id=user_id, course_id=course_id)
        totals = {"jobs": 0, "created": 0, "reinforced": 0}
        for _ in range(4):
            result = await self.process_next_batch(
                user_id=user_id, course_id=course_id, include_recent=True,
            )
            for key in totals:
                totals[key] += result[key]
            if not result["jobs"]:
                break
        return totals
