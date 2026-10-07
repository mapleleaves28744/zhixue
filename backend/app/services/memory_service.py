from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.learning_record import LearningRecord
from app.models.memory import MemoryReflectionState, StudentMemory, StudentMemoryEvent, StudentMemoryEvidence
from app.models.user import User
from app.repositories.agent_conversation_repository import AgentConversationRepository
from app.repositories.memory_repository import MemoryRepository
from app.services.memory_facts import canonical_preference, likely_same_fact
from app.schemas.memory import MemoryHealth, MemoryRead, MemoryUpdate


class MemoryService:
    COURSE_CAPACITY = 20
    GLOBAL_CAPACITY = 10

    @staticmethod
    def normalize_evidence(value: Any) -> list[Any]:
        from app.schemas.memory import _normalize_evidence

        return _normalize_evidence(value)

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_memories(
        self,
        user_id: UUID,
        course_id: UUID | None = None,
        memory_type: str | None = None,
        status: str = "active",
        limit: int | None = None,
    ) -> list[MemoryRead]:
        stmt = select(StudentMemory).where(StudentMemory.user_id == user_id)
        if course_id is not None:
            stmt = stmt.where(StudentMemory.course_id == course_id)
        if memory_type is not None:
            stmt = stmt.where(StudentMemory.memory_type == memory_type)
        if status != "all":
            stmt = stmt.where(StudentMemory.status == status)
        stmt = stmt.order_by(
            StudentMemory.salience.desc(),
            StudentMemory.confidence.desc(),
            StudentMemory.last_reinforced_at.desc().nullslast(),
            StudentMemory.updated_at.desc(),
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        return [MemoryRead.model_validate(m) for m in result.scalars().all()]

    @classmethod
    def build_memory_key(cls, memory_type: str, content: str) -> str:
        normalized = re.sub(r"\s+", " ", content.strip().lower())
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
        return f"{memory_type}:{digest}"

    @staticmethod
    def build_fact_key(memory_type: str, content: str, legacy_key: str) -> str:
        if memory_type == "preference":
            canonical = canonical_preference(content)
            if canonical:
                return "preference:detail" if canonical.endswith((":concise", ":detailed")) else canonical
        normalized = re.sub(r"\s+", "", content.strip().casefold())
        normalized = re.sub(r"[，。！？、,.!?;；:：\[\]()（）]", "", normalized)
        candidate = f"{memory_type}:{normalized}"
        return candidate if len(candidate) <= 255 else legacy_key

    @classmethod
    def active_capacity(cls, course_id: object | None) -> int:
        return cls.COURSE_CAPACITY if course_id is not None else cls.GLOBAL_CAPACITY

    async def upsert_memory(
        self,
        *,
        user_id: UUID,
        course_id: UUID | None,
        memory_type: str,
        content: str,
        evidence: list[Any],
        confidence: float,
        salience: float | None = None,
        suggested_action: str = "add",
        related_memory_id: UUID | None = None,
    ) -> tuple[StudentMemory, str]:
        evidence = self.normalize_evidence(evidence)
        key = self.build_memory_key(memory_type, content)
        fact_key = self.build_fact_key(memory_type, content, key)
        await self.db.execute(select(User.id).where(User.id == user_id).with_for_update())
        condition = [
            StudentMemory.user_id == user_id,
            or_(StudentMemory.fact_key == fact_key, StudentMemory.memory_key == key),
        ]
        condition.append(StudentMemory.course_id == course_id if course_id is not None else StudentMemory.course_id.is_(None))
        existing = (await self.db.execute(
            select(StudentMemory).where(*condition).order_by(
                (StudentMemory.status == "active").desc(),
                StudentMemory.confidence.desc(),
                StudentMemory.updated_at.desc(),
            ).limit(1).execution_options(populate_existing=True)
        )).scalar_one_or_none()
        now = datetime.now(UTC)
        candidates = await MemoryRepository(self.db).reconciliation_candidates(user_id, course_id)
        pending_reason = None
        related = next((item for item in candidates if item.id == related_memory_id), None)
        pending_duplicate = next((item for item in candidates if item.status == "pending"
                                  and item.memory_type == memory_type and item.content == content), None)
        if pending_duplicate:
            return pending_duplicate, "skipped"
        for item in candidates:
            same_key = self.build_fact_key(item.memory_type, item.content, item.memory_key) == fact_key
            if item.status == "forgotten" and item.memory_type == memory_type:
                aliases = list((item.lifecycle_meta or {}).get("aliases") or [])
                if same_key or content in aliases:
                    return item, "skipped"
                if likely_same_fact(item.content, content):
                    pending_reason = "possible_forgotten_fact"
                elif memory_type == "preference" and (
                    canonical_preference(item.content) is None or canonical_preference(content) is None
                ):
                    # An unfamiliar paraphrase cannot prove it is a different
                    # preference. Keep it out of active recall until confirmed.
                    pending_reason = "possible_forgotten_fact"
            if item.status == "active" and item.course_id == course_id and same_key and memory_type == "preference":
                old_value, new_value = canonical_preference(item.content), canonical_preference(content)
                if old_value and new_value and old_value != new_value:
                    pending_reason = "conflicting_candidate_requires_confirmation"
                    related = item
                    related_memory_id = item.id
        if related_memory_id is not None and related is None:
            # Model-selected IDs must belong to this user's scope.
            pending_reason = "unknown_related_memory"
        elif related is not None:
            if related.status != "active":
                return related, "skipped"
            if suggested_action == "reinforce" and related.memory_type == memory_type:
                existing = related
            elif suggested_action in {"dispute", "supersede"}:
                pending_reason = "conflicting_candidate_requires_confirmation"
        if existing is None and not pending_reason:
            existing = next((item for item in candidates if item.course_id == course_id
                             and item.memory_type == memory_type
                             and self.build_fact_key(item.memory_type, item.content, item.memory_key) == fact_key), None)
        if existing is not None:
            if existing.status != "active":
                # A background reflection cannot undo a user action or a capacity archive.
                return existing, "skipped"
            if pending_reason:
                existing = None
        if existing is not None:
            new_evidence = [item for item in evidence if item not in (existing.evidence or [])]
            if not new_evidence:
                return existing, "skipped"
            before = self._snapshot(existing)
            existing.evidence = self._merge_evidence(existing.evidence or [], evidence)
            existing.lifecycle_meta = {**(existing.lifecycle_meta or {}), "aliases": list(dict.fromkeys(
                [*(existing.lifecycle_meta or {}).get("aliases", []), existing.content, content]
            ))[-20:]}
            existing.confidence = max(float(existing.confidence), confidence)
            existing.salience = max(float(existing.salience), salience if salience is not None else confidence)
            existing.reinforcement_count += 1
            existing.last_reinforced_at = now
            # A model supplied alias must not replace the established fact identity.
            existing.fact_key = existing.fact_key or fact_key
            existing.revision += 1
            action = "reinforce"
            memory = existing
        else:
            before = {}
            memory = StudentMemory(
                user_id=user_id,
                course_id=course_id,
                memory_type=memory_type,
                memory_key=key,
                fact_key=fact_key,
                origin="reflection",
                status="pending" if pending_reason else "active",
                lifecycle_meta={"tier": "hot", "scope": "course" if course_id else "global",
                                **({"review_reason": pending_reason, "related_memory_id": str(related_memory_id or "")}
                                   if pending_reason else {})},
                content=content,
                evidence=evidence,
                confidence=confidence,
                salience=salience if salience is not None else confidence,
                last_reinforced_at=now,
            )
            self.db.add(memory)
            action = "pending" if pending_reason else "add"
        await self.db.flush()
        await self._record_change(memory, action=action, actor="reflection", before=before, source_refs=evidence)
        if action == "pending" and suggested_action == "dispute" and related is not None:
            await self._record_change(related, action="dispute_candidate", actor="reflection",
                                      before=self._snapshot(related), source_refs=evidence, stance="refute")
        await self._advance_revision(user_id=user_id, course_id=course_id)
        await self.enforce_capacity(user_id=user_id, course_id=course_id)
        return memory, action

    async def enforce_capacity(self, *, user_id: UUID, course_id: UUID | None) -> None:
        condition = [StudentMemory.user_id == user_id, StudentMemory.status == "active"]
        condition.append(StudentMemory.course_id == course_id if course_id is not None else StudentMemory.course_id.is_(None))
        rows = list((await self.db.execute(select(StudentMemory).where(*condition).order_by(
            StudentMemory.salience.desc(), StudentMemory.confidence.desc(), StudentMemory.updated_at.desc()
        ))).scalars().all())
        for index, item in enumerate(rows):
            tier = "hot" if index < self.active_capacity(course_id) else "cold"
            if (item.lifecycle_meta or {}).get("tier") != tier:
                item.lifecycle_meta = {**(item.lifecycle_meta or {}), "tier": tier}

    async def health(self, user_id: UUID, course_id: UUID | None) -> MemoryHealth:
        condition = [StudentMemory.user_id == user_id]
        condition.append(StudentMemory.course_id == course_id if course_id is not None else StudentMemory.course_id.is_(None))
        rows = (await self.db.execute(select(StudentMemory.status, func.count()).where(*condition).group_by(StudentMemory.status))).all()
        counts = {str(status): int(count) for status, count in rows}
        capacity = self.active_capacity(course_id)
        hot = (await self.db.execute(select(func.count()).select_from(StudentMemory).where(
            *condition, StudentMemory.status == "active",
            func.coalesce(StudentMemory.lifecycle_meta["tier"].astext, "hot") != "cold",
        ))).scalar_one()
        active = counts.get("active", 0)
        return MemoryHealth(active_count=active, hot_count=hot, cold_count=max(0, active - hot), archived_count=counts.get("archived", 0), capacity=capacity, remaining=max(0, capacity - hot))

    async def restore_memory(self, memory_id: UUID, user_id: UUID) -> MemoryRead:
        await self.db.execute(select(User.id).where(User.id == user_id).with_for_update())
        memory = await self._get_owned(memory_id, user_id)
        if memory.status == "pending" and (memory.lifecycle_meta or {}).get("review_reason") == "conflicting_candidate_requires_confirmation":
            related_id = (memory.lifecycle_meta or {}).get("related_memory_id")
            related = await self._get_owned(UUID(related_id), user_id) if related_id else None
            if related and related.course_id == memory.course_id and related.status == "active":
                prior = self._snapshot(related)
                related.status = "superseded"
                related.lifecycle_meta = {**(related.lifecycle_meta or {}), "superseded_by": str(memory.id)}
                await self._record_change(related, action="supersede", actor="user", before=prior)
                await self.db.flush()
        await self._reject_active_fact_conflict(memory, restoring=True)
        before = self._snapshot(memory)
        memory.status = "active"
        memory.archived_at = None
        memory.last_reinforced_at = datetime.now(UTC)
        memory.revision += 1
        memory.lifecycle_meta = {**(memory.lifecycle_meta or {}), "tombstone": False, "tier": "hot"}
        await self._record_change(memory, action="restore", actor="user", before=before)
        await self._advance_revision(user_id=user_id, course_id=memory.course_id)
        await self.enforce_capacity(user_id=user_id, course_id=memory.course_id)
        await AgentConversationRepository(self.db).invalidate_context_summaries(
            user_id=user_id, course_id=memory.course_id,
        )
        await self.db.commit()
        await self.db.refresh(memory)
        return MemoryRead.model_validate(memory)

    async def reflect(self, user_id: UUID, course_id: UUID | None = None) -> list[MemoryRead]:
        from app.agents.context import AgentContext
        from app.agents.memory_agent import MemoryAgent

        agent = MemoryAgent(self.db)
        context = AgentContext(
            user_id=user_id,
            course_id=course_id or user_id,
            task_type="memory_reflect",
            params={"action": "reflect", "course_id": str(course_id) if course_id else None},
        )
        result = await agent.run(context)
        if not result.success:
            raise BusinessException(
                code=ErrorCode.LLM_CALL_FAILED,
                detail=result.message,
                status_code=500,
            )
        return await self.list_memories(user_id, course_id)

    async def delete_memory(self, memory_id: UUID, user_id: UUID) -> None:
        await self.db.execute(select(User.id).where(User.id == user_id).with_for_update())
        memory = await self._get_owned(memory_id, user_id)
        before = self._snapshot(memory)
        memory.status = "forgotten"
        memory.archived_at = datetime.now(UTC)
        memory.revision += 1
        memory.lifecycle_meta = {**(memory.lifecycle_meta or {}), "tombstone": True, "archive_reason": "user_forget"}
        await self._record_change(memory, action="forget", actor="user", before=before)
        await self._advance_revision(user_id=user_id, course_id=memory.course_id)
        await AgentConversationRepository(self.db).invalidate_context_summaries(
            user_id=user_id, course_id=memory.course_id,
        )
        await self.db.commit()

    async def update_memory(
        self, memory_id: UUID, user_id: UUID, payload: MemoryUpdate
    ) -> MemoryRead:
        await self.db.execute(select(User.id).where(User.id == user_id).with_for_update())
        stmt = select(StudentMemory).where(
            StudentMemory.id == memory_id,
            StudentMemory.user_id == user_id,
        ).execution_options(populate_existing=True)
        result = await self.db.execute(stmt)
        memory = result.scalar_one_or_none()
        if memory is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="记忆不存在",
                status_code=404,
            )
        if memory.status == "forgotten":
            raise BusinessException(code=ErrorCode.CONFLICT, detail="已遗忘的记忆需先恢复才能修正", status_code=409)
        before = self._snapshot(memory)
        values = payload.model_dump(exclude_unset=True)
        if any(value is None or not str(value).strip() for value in values.values()):
            raise BusinessException(code=ErrorCode.PARAM_ERROR, detail="记忆内容和类型不能为空", status_code=400)
        for key, value in values.items():
            setattr(memory, key, value)
        if values.get("status") == "archived":
            memory.archived_at = datetime.now(UTC)
            memory.lifecycle_meta = {**(memory.lifecycle_meta or {}), "archive_reason": "user_archive"}
        memory.memory_key = self.build_memory_key(memory.memory_type, memory.content)
        memory.fact_key = self.build_fact_key(memory.memory_type, memory.content, memory.memory_key)
        await self._reject_active_fact_conflict(memory)
        memory.revision += 1
        await self._record_change(memory, action="correct", actor="user", before=before)
        await self._advance_revision(user_id=user_id, course_id=memory.course_id)
        await self.db.commit()
        await self.db.refresh(memory)
        return MemoryRead.model_validate(memory)

    async def _get_owned(self, memory_id: UUID, user_id: UUID) -> StudentMemory:
        result = await self.db.execute(select(StudentMemory).where(StudentMemory.id == memory_id, StudentMemory.user_id == user_id).execution_options(populate_existing=True))
        memory = result.scalar_one_or_none()
        if memory is None:
            raise BusinessException(code=ErrorCode.NOT_FOUND, detail="记忆不存在", status_code=404)
        return memory

    def _merge_evidence(self, existing: list[Any], incoming: list[Any]) -> list[Any]:
        merged: list[Any] = []
        seen: set[str] = set()
        for item in existing + incoming:
            key = repr(item)
            if key not in seen:
                seen.add(key)
                merged.append(item)
        return merged[-20:]

    @staticmethod
    def _snapshot(memory: StudentMemory) -> dict[str, Any]:
        return {
            "content": memory.content, "memory_type": memory.memory_type,
            "fact_key": memory.fact_key, "status": memory.status,
            "confidence": float(memory.confidence), "evidence": list(memory.evidence or []),
            "revision": memory.revision, "lifecycle_meta": dict(memory.lifecycle_meta or {}),
        }

    async def _record_change(
        self, memory: StudentMemory, *, action: str, actor: str,
        before: dict[str, Any], source_refs: list[Any] | None = None, stance: str = "support",
    ) -> None:
        self.db.add(StudentMemoryEvent(
            memory_id=memory.id, operation_id=uuid4(), actor=actor, action=action,
            before_snapshot=before, after_snapshot=self._snapshot(memory),
            source_refs=source_refs or [],
        ))
        for source in source_refs or []:
            try:
                source_id = UUID(str(source))
            except ValueError:
                continue
            record = (await self.db.execute(select(LearningRecord.id).where(
                LearningRecord.id == source_id, LearningRecord.user_id == memory.user_id,
            ))).scalar_one_or_none()
            if record is None:
                continue
            prior = (await self.db.execute(select(StudentMemoryEvidence.id).where(
                StudentMemoryEvidence.memory_id == memory.id,
                StudentMemoryEvidence.source_type == "learning_record",
                StudentMemoryEvidence.source_id == source_id,
                StudentMemoryEvidence.stance == stance,
            ))).scalar_one_or_none()
            if prior is None:
                self.db.add(StudentMemoryEvidence(
                    memory_id=memory.id, source_type="learning_record",
                    source_id=source_id, stance=stance,
                ))

    async def _advance_revision(self, *, user_id: UUID, course_id: UUID | None) -> None:
        scope = [MemoryReflectionState.user_id == user_id]
        scope.append(MemoryReflectionState.course_id == course_id if course_id else MemoryReflectionState.course_id.is_(None))
        state = (await self.db.execute(select(MemoryReflectionState).where(*scope).with_for_update())).scalar_one_or_none()
        if state is None:
            state = MemoryReflectionState(user_id=user_id, course_id=course_id, memory_revision=1)
            self.db.add(state)
        else:
            state.memory_revision += 1
        await self.db.flush()

    async def _reject_active_fact_conflict(self, memory: StudentMemory, *, restoring: bool = False) -> None:
        if memory.status != "active" and not restoring:
            return
        scope = [
            StudentMemory.user_id == memory.user_id,
            StudentMemory.id != memory.id,
            StudentMemory.status == "active",
            StudentMemory.fact_key == memory.fact_key,
        ]
        scope.append(StudentMemory.course_id == memory.course_id if memory.course_id else StudentMemory.course_id.is_(None))
        with self.db.no_autoflush:
            existing = (await self.db.execute(select(StudentMemory.id).where(*scope))).scalar_one_or_none()
        if existing is not None:
            raise BusinessException(code=ErrorCode.CONFLICT, detail="同一范围内已有相同学习记忆", status_code=409)

    async def evidence_records(self, memory_id: UUID, user_id: UUID) -> list[dict[str, Any]]:
        memory = await self._get_owned(memory_id, user_id)
        records = await MemoryRepository(self.db).evidence_records(memory)
        return [{"source_id": str(item.id), "event_type": item.event_type,
                 "created_at": item.created_at.isoformat(),
                 "excerpt": str((item.event_payload or {}).get("question") or
                                (item.event_payload or {}).get("summary") or item.event_type)[:1000]}
                for item in records]
