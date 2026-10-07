"""Asynchronous, source-preserving semantic selection with projection fencing."""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.models.agent_conversation import AgentConversation
from app.repositories.agent_conversation_repository import AgentConversationRepository
from app.services.prompt_service import PromptService
from app.llm.provider import get_llm_provider
from app.llm.schemas import ChatMessage
from app.core.config import settings


class SummarySelection(BaseModel):
    selected_indices: list[int] = Field(default_factory=list, min_length=1, max_length=16)


def selected_excerpt(lines: list[str], indices: list[int]) -> str:
    if any(index < 0 or index >= len(lines) for index in indices):
        raise ValueError("summary referenced a nonexistent source")
    # Preserve the opening goal regardless of model selection; emit original text only.
    chosen = list(dict.fromkeys([*range(min(4, len(lines))), *indices]))
    return "\n".join(lines[index] for index in chosen)[:2400]


class SemanticSummaryService:
    def __init__(self, db: Any) -> None:
        self.db = db

    async def compact(self, conversation_id: UUID, user_id: UUID) -> bool:
        repository = AgentConversationRepository(self.db)
        conversation = await repository.get_for_user(conversation_id, user_id)
        if not conversation:
            return False
        meta = dict((conversation.extra_meta or {}).get("context_compaction_v1") or {})
        version = int(meta.get("version") or 0)
        if not version or meta.get("semantic_version") == version:
            return False
        raw = str(meta.get("raw_summary") or conversation.summary or "")
        lines = raw.splitlines()
        if not lines:
            return False
        course_id = conversation.course_id
        await self.db.commit()  # No conversation lock is held across the model call.
        prompt = await PromptService(self.db).render_prompt(
            agent_name="OrchestratorAgent", scene="context.select_summary",
            params={"lines": json.dumps(dict(enumerate(lines)), ensure_ascii=False)},
        )
        provider = get_llm_provider(db=self.db, user_id=user_id, course_id=course_id, allow_mock_fallback=False)
        result = await provider.structured_chat(
            [ChatMessage(role="user", content=prompt.content)], SummarySelection,
            temperature=0, max_tokens=400, max_retries=1, prompt_version_id=prompt.prompt_version_id,
        )
        excerpt = selected_excerpt(lines, result.selected_indices)
        current = await repository.get_for_user_locked(conversation_id, user_id)
        current_meta = dict((current.extra_meta or {}).get("context_compaction_v1") or {}) if current else {}
        if not current or current_meta.get("version") != version or str(current_meta.get("raw_summary") or current.summary or "") != raw:
            await self.db.rollback()
            return False  # Forget, a newer projection or course change won the race.
        current.summary = excerpt
        current.extra_meta = {**(current.extra_meta or {}), "context_compaction_v1": {
            **current_meta, "raw_summary": raw, "semantic_version": version,
            "semantic_source_indices": result.selected_indices, "semantic_method": "source_selection_v1",
        }}
        await self.db.commit()
        return True

    async def process_pending(self, limit: int = 3) -> int:
        if settings.llm_provider == "mock" or not settings.llm_api_key:
            return 0
        projection = AgentConversation.extra_meta["context_compaction_v1"]
        rows = (await self.db.execute(select(AgentConversation.id, AgentConversation.user_id).where(
            projection["version"].astext.is_not(None),
            projection["version"].astext != projection["semantic_version"].astext,
        ).limit(limit))).all()
        # SQL NULL needs an explicit branch for first-time semantic selection.
        if not rows:
            rows = (await self.db.execute(select(AgentConversation.id, AgentConversation.user_id).where(
                projection["version"].astext.is_not(None), projection["semantic_version"].astext.is_(None),
            ).limit(limit))).all()
        completed = 0
        for conversation_id, user_id in rows:
            try:
                completed += await self.compact(conversation_id, user_id)
            except Exception:
                await self.db.rollback()
        return completed
