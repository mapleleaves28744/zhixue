from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.agent_conversation_repository import AgentConversationRepository
from app.services.conversation_turns import completed_turn_blocks
from app.services.conversation_constraints import apply_session_changes, parse_session_changes
from app.services.memory_suppression_service import MemorySuppressionService


_STABLE_PREFERENCE = re.compile(r"(?:我喜欢|我更喜欢|我的偏好|以后请|请一直|记住|忘记)")
_CITATION = re.compile(r"\[S\d+\]")


class ConversationSummaryService:
    """Advance a bounded projection over committed, complete conversation turns."""

    MIN_COMPLETE_TURNS = 14
    KEEP_RECENT_TURNS = 6
    MAX_SUMMARY_CHARS = 6000

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.conversations = AgentConversationRepository(db)

    async def maybe_compact(self, *, conversation_id: UUID, user_id: UUID) -> bool:
        conversation = await self.conversations.get_for_user_locked(conversation_id, user_id)
        if conversation is None:
            return False
        meta = dict((conversation.extra_meta or {}).get("context_compaction_v1") or {})
        covered = int(meta.get("covered_through_sequence") or 0)
        original_covered = covered
        summary_lines = str(meta.get("raw_summary") or conversation.summary or "").splitlines()
        session_constraints = dict(meta.get("session_constraints") or {})
        suppressed_records = await MemorySuppressionService(self.db).source_record_ids(
            user_id=user_id, course_id=conversation.course_id,
        )
        if covered and "session_constraints" not in meta:
            from app.services.conversation_context_service import ConversationContextService

            session_constraints = await ConversationContextService(self.db)._replay_session_constraints(
                conversation_id=conversation_id,
                before_sequence=covered + 1,
                suppressed_records=suppressed_records,
            )
        for _ in range(10):
            rows = await self.conversations.list_messages_after_sequence(conversation_id, covered, limit=120)
            blocks = self._closed_blocks(rows, suppressed_records)
            complete_turns = sum(turns for _, turns, _, _ in blocks)
            if complete_turns < self.MIN_COMPLETE_TURNS:
                break
            chosen: list[tuple[int, int, list[str], list[str]]] = []
            chosen_turns = 0
            for block in blocks:
                if complete_turns - chosen_turns - block[1] < self.KEEP_RECENT_TURNS:
                    break
                chosen.append(block)
                chosen_turns += block[1]
                if chosen_turns >= 8:
                    break
            if not chosen:
                break
            for _, _, users, artifacts in chosen:
                summary_lines.extend(f"学生原话：{item}" for item in users)
                summary_lines.extend(f"已生成产物：{item}" for item in artifacts)
            new_covered = chosen[-1][0]
            for boundary, turns in completed_turn_blocks(rows):
                if boundary > new_covered:
                    break
                for turn in turns:
                    assistant_payload = getattr(turn.assistant, "payload", {}) or {}
                    if str(assistant_payload.get("learning_record_id") or "") in suppressed_records:
                        continue
                    session_constraints = apply_session_changes(
                        session_constraints,
                        text=str(getattr(turn.user, "content", "") or ""),
                        source=turn.user,
                    )
            covered = new_covered
        if covered == original_covered:
            await self.db.rollback()
            return False
        summary_lines, dropped = self._bound_lines(summary_lines)
        conversation.summary = "\n".join(summary_lines)
        conversation.extra_meta = {
            **(conversation.extra_meta or {}),
            "context_compaction_v1": {
                "version": int(meta.get("version") or 0) + 1,
                "covered_through_sequence": covered,
                "first_kept_sequence": covered + 1,
                "source_revision": conversation.next_message_sequence,
                "dropped_line_count": int(meta.get("dropped_line_count") or 0) + dropped,
                "generated_at": datetime.now(UTC).isoformat(),
                "session_constraints": session_constraints,
                "raw_summary": conversation.summary,
            },
        }
        latest = await self.conversations.get_message_by_sequence(
            conversation_id, conversation.next_message_sequence,
        )
        if latest is not None and latest.role == "assistant":
            latest.payload = {
                **(latest.payload or {}),
                "context_compaction": {
                    "version": int(meta.get("version") or 0) + 1,
                    "covered_through_sequence": covered,
                    "first_kept_sequence": covered + 1,
                },
            }
        await self.db.commit()
        return True

    @staticmethod
    def _closed_blocks(
        rows: list[object], suppressed_records: set[str] | None = None,
    ) -> list[tuple[int, int, list[str], list[str]]]:
        blocks: list[tuple[int, int, list[str], list[str]]] = []
        suppressed_records = suppressed_records or set()
        for boundary, turns in completed_turn_blocks(rows):
            users: list[str] = []
            artifacts: list[str] = []
            for turn in turns:
                assistant_payload = getattr(turn.assistant, "payload", {}) or {}
                if str(assistant_payload.get("learning_record_id") or "") in suppressed_records:
                    continue
                content = " ".join(str(getattr(turn.user, "content", "")).split())[:160]
                if content and not _STABLE_PREFERENCE.search(content) and not parse_session_changes(content):
                    users.append(_CITATION.sub("〔历史引用〕", content))
                for artifact in list(assistant_payload.get("artifacts") or [])[:3]:
                    if not isinstance(artifact, dict):
                        continue
                    kind = str(artifact.get("type") or "")[:32]
                    artifact_id = str(artifact.get("id") or artifact.get("asset_id") or "")[:80]
                    title = str(artifact.get("title") or "")[:60]
                    if kind and artifact_id:
                        artifacts.append(f"{kind} {artifact_id} {title}".strip())
            blocks.append((boundary, len(turns), users, artifacts))
        return blocks

    @classmethod
    def _bound_lines(cls, lines: list[str]) -> tuple[list[str], int]:
        if len("\n".join(lines)) <= cls.MAX_SUMMARY_CHARS:
            return lines, 0
        keep = lines[:4] + lines[-24:]
        while len("\n".join(keep)) > cls.MAX_SUMMARY_CHARS and len(keep) > 4:
            keep.pop(4)
        return keep, len(lines) - len(keep)
