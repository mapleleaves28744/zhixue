from __future__ import annotations

import re
import ipaddress
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.llm.schemas import ChatMessage
from app.repositories.agent_conversation_repository import AgentConversationRepository
from app.services.context_budget import estimate_tokens, input_token_limit, truncate_to_tokens
from app.services.conversation_turns import completed_turn_blocks
from app.services.conversation_constraints import apply_session_changes, render_session_constraints
from app.services.memory_suppression_service import MemorySuppressionService


_FOLLOW_UP = re.compile(r"^(?:那|那么|再|继续|刚才|上面|这个|那个|它|其|第[一二三四五六七八九十\d]+个|为什么|怎么|能否|可以|换个|换一种|举个|举一个|给我|来个|反例|详细|具体)")
_OLD_CITATION = re.compile(r"\[S(\d+)\]")
_WEB_ORDINAL = re.compile(r"第\s*(\d+|[一二三四五六七八九十])\s*(?:个|条)?\s*(?:链接|网页|搜索结果)")
_QUIZ_OPTION = re.compile(r"(?:第\s*(\d+|[一二三四五六七八九十])\s*(?:个|项)?\s*选项|选项\s*([A-Da-d]))")
_MATERIAL_REFERENCE = re.compile(r"(?:刚才|上面|之前|上一|那份|那篇|这份|这篇).{0,8}(?:资料|文档|讲义|文件)|第\s*(?:\d+|[一二三四五六七八九十])\s*(?:份|个|篇)?\s*(?:资料|文档|讲义|文件)")
_RESOURCE_REVISION = re.compile(
    r"(?:修改|改写|重写|调整|优化|补充).{0,20}(?:刚才|上个|上一个|上一份|上一版|前一个|上面).{0,12}(?:资源|产物|课件|讲解|总结)"
    r"|(?:把|将).{0,16}(?:刚才|上个|上一个|上一份|上一版|前一个|上面).{0,12}(?:资源|产物|课件|讲解|总结).{0,8}(?:改|调整|重写|优化|补充)"
)
_CHINESE_ORDINALS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _public_web_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
            return False
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return True
    except ValueError:
        return False


@dataclass(frozen=True)
class ConversationContext:
    history: tuple[tuple[str, str], ...] = ()
    last_question: str | None = None
    older_user_requests: tuple[str, ...] = ()
    summary: str = ""
    summary_version: int = 0
    active_constraints: dict[str, dict[str, Any]] = field(default_factory=dict)
    web_references: tuple[dict[str, str], ...] = ()
    quiz_reference: dict[str, str] | None = None
    material_references: tuple[dict[str, Any], ...] = ()
    resource_references: tuple[dict[str, Any], ...] = ()

    @staticmethod
    def requested_web_ordinal(question: str) -> int | None:
        match = _WEB_ORDINAL.search(question)
        if match is None:
            return None
        value = match.group(1)
        return int(value) if value.isdigit() else _CHINESE_ORDINALS.get(value)

    def resolve_web_reference(self, question: str) -> dict[str, str] | None:
        index = self.requested_web_ordinal(question)
        if index is None or index < 1 or index > len(self.web_references):
            return None
        reference = self.web_references[index - 1]
        return reference if _public_web_url(reference["url"]) else None

    @staticmethod
    def requested_quiz_option(question: str) -> int | None:
        if not re.search(r"上题|上一题|刚才.*题|第\s*[一二三四五六七八九十\d]+\s*题", question):
            return None
        match = _QUIZ_OPTION.search(question)
        if match is None:
            return None
        value = match.group(1)
        return (int(value) if value.isdigit() else _CHINESE_ORDINALS.get(value)) if value else ord(match.group(2).upper()) - ord("A") + 1

    @staticmethod
    def requested_quiz_question(question: str) -> int | None:
        match = re.search(r"第\s*(\d+|[一二三四五六七八九十])\s*题", question)
        if not match:
            return None
        value = match.group(1)
        return int(value) if value.isdigit() else _CHINESE_ORDINALS[value]

    @staticmethod
    def requested_material_reference(question: str) -> bool:
        return bool(_MATERIAL_REFERENCE.search(question))

    def resolve_material_reference(self, question: str) -> dict[str, Any] | None:
        match = re.search(r"第\s*(\d+|[一二三四五六七八九十])\s*(?:份|个|篇)?\s*(?:资料|文档|讲义|文件)", question)
        if match:
            raw = match.group(1)
            ordinal = int(raw) if raw.isdigit() else _CHINESE_ORDINALS[raw]
            return self.material_references[ordinal - 1] if 1 <= ordinal <= len(self.material_references) else None
        named = [item for item in self.material_references if len(str(item.get("title") or "")) >= 2
                 and str(item["title"]) in question]
        if len(named) == 1:
            return named[0]
        return self.material_references[0] if len(self.material_references) == 1 else None

    @staticmethod
    def requested_resource_revision(question: str) -> bool:
        return bool(_RESOURCE_REVISION.search(question))

    def resolve_query(self, question: str) -> str:
        current = question.strip()
        if self.last_question and _FOLLOW_UP.match(current):
            return f"上文讨论：{self.last_question[:240]}。本轮追问：{current}"
        return current

    def render(self) -> str:
        constraints = render_session_constraints(self.active_constraints)
        if not self.history and not self.older_user_requests and not self.summary and not constraints:
            return ""
        lines = ["以下是同一会话中已经完成的对话，仅用于理解指代和学生的当前要求。历史回答不是本轮课程依据；历史引用编号不能作为本轮 [S#] 引用。"]
        if constraints:
            lines.append("学生在本会话明确提出的持续要求：" + constraints)
        if self.summary:
            lines.append("更早回合的持久摘录：" + self.summary)
        if self.older_user_requests:
            lines.append("更早的学生原话摘要：" + "；".join(self.older_user_requests))
        for role, content in self.history:
            safe_content = _OLD_CITATION.sub(r"〔历史引用 S\1〕", content[:700])
            lines.append(f"{'学生' if role == 'user' else '助手'}：{safe_content}")
        return "\n".join(lines)

    def messages_for(self, current_prompt: str, *, max_input_tokens: int | None = None) -> list[ChatMessage]:
        constraints = render_session_constraints(self.active_constraints)
        input_limit = max_input_tokens if max_input_tokens is not None else input_token_limit(output_reserve=1200)
        if estimate_tokens(current_prompt) > input_limit:
            raise BusinessException(code=ErrorCode.PARAM_ERROR, detail="当前问题与资料超过上下文预算，请缩小资料范围或分批处理。", status_code=400)
        if not self.history and not self.older_user_requests and not self.summary and not constraints:
            return [ChatMessage(role="user", content=current_prompt)]
        instruction = ChatMessage(
            role="system",
            content="历史对话仅用于理解当前指代和学习要求。历史回答不是本轮已核验的课程依据；本轮只能引用当前证据包中的 [S#]。出现冲突时，以学生较新的明确要求为准。",
        )
        # The current request and evidence prompt are mandatory. Allocate only the
        # remaining capacity to history, retaining complete recent turns.
        remaining = min(
            6000,
            max(0, input_limit - estimate_tokens(current_prompt) - estimate_tokens(instruction.content) - 64),
        )
        constraint_message = (
            ChatMessage(role="user", content="学生在本会话明确提出的持续要求：" + constraints)
            if constraints else None
        )
        if constraint_message is not None:
            remaining = max(0, remaining - estimate_tokens(constraint_message.content))
        mandatory_cost = estimate_tokens(current_prompt) + estimate_tokens(instruction.content) + 64
        if constraint_message is not None:
            mandatory_cost += estimate_tokens(constraint_message.content)
        if mandatory_cost > input_limit:
            raise BusinessException(code=ErrorCode.PARAM_ERROR, detail="当前问题与持续要求超过上下文预算，请分批处理。", status_code=400)
        # Reserve room for the earlier goal before recent verbose assistant turns
        # can consume the entire optional history allocation.
        summary_allowance = min(1200, remaining // 3) if self.summary or self.older_user_requests else 0
        history_remaining = remaining - summary_allowance
        blocks = [self.history[index:index + 2] for index in range(0, len(self.history) - 1, 2)]
        kept: list[tuple[ChatMessage, ChatMessage]] = []
        for block in reversed(blocks):
            if [role for role, _ in block] != ["user", "assistant"]:
                continue
            pair = tuple(
                ChatMessage(role=role, content=_OLD_CITATION.sub(r"〔历史引用 S\1〕", content[:700]))
                for role, content in block
            )
            cost = sum(estimate_tokens(item.content) for item in pair)
            if cost > history_remaining:
                break
            kept.append(pair)
            remaining -= cost
            history_remaining -= cost
        messages = [instruction]
        if constraint_message is not None:
            messages.append(constraint_message)
        if remaining > 64 and (self.summary or self.older_user_requests):
            lines = []
            if self.summary:
                lines.append("更早回合的持久摘录：\n" + self.summary[:2400])
            if self.older_user_requests:
                lines.append("较早学生原话：" + "；".join(self.older_user_requests))
            brief = truncate_to_tokens("\n".join(lines), remaining)
            if brief:
                messages.append(ChatMessage(role="user", content=brief))
        for pair in reversed(kept):
            messages.extend(pair)
        messages.append(ChatMessage(role="user", content=current_prompt))
        return messages


class ConversationContextService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.conversations = AgentConversationRepository(db)

    async def load(
        self,
        *,
        conversation_id: UUID | None,
        user_id: UUID,
        course_id: UUID,
        before_sequence: int | None = None,
    ) -> ConversationContext:
        if conversation_id is None:
            return ConversationContext()
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if conversation is None or conversation.course_id != course_id:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="当前课程的会话不存在",
                status_code=404,
            )
        meta = dict((getattr(conversation, "extra_meta", {}) or {}).get("context_compaction_v1") or {})
        covered = int(meta.get("covered_through_sequence") or 0)
        replay_constraints = before_sequence is not None and covered >= before_sequence
        if replay_constraints:
            # The current projection includes later turns. Rebuild a bounded view from
            # original messages so a queued task cannot read conversation future.
            covered = 0
            summary = ""
            summary_version = 0
            active_constraints: dict[str, dict[str, Any]] = {}
        else:
            summary = str(getattr(conversation, "summary", "") or "")
            summary_version = int(meta.get("version") or 0)
            active_constraints = dict(meta.get("session_constraints") or {}) if covered else {}
        if before_sequence is None:
            messages = await self.conversations.list_messages(conversation_id, limit=80)
        else:
            messages = await self.conversations.list_messages(
                conversation_id, limit=80, before_sequence=before_sequence,
            )
        if covered:
            messages = [item for item in messages if int(getattr(item, "sequence_no", 0)) > covered]
        suppressed_records = (
            await MemorySuppressionService(self.db).source_record_ids(user_id=user_id, course_id=course_id)
            if hasattr(self.db, "execute") else set()
        )
        needs_full_replay = (
            replay_constraints
            or (covered and "session_constraints" not in meta)
            or (not covered and int(getattr(conversation, "next_message_sequence", 0) or 0) > 80)
        )
        if needs_full_replay:
            active_constraints = await self._replay_session_constraints(
                conversation_id=conversation_id,
                before_sequence=before_sequence or (covered + 1 if covered else int(conversation.next_message_sequence) + 1),
                suppressed_records=suppressed_records,
            )
        completed: list[tuple[str, str]] = []
        web_references: tuple[dict[str, str], ...] = ()
        quiz_reference: dict[str, str] | None = None
        material_references: tuple[dict[str, Any], ...] = ()
        resource_references: tuple[dict[str, Any], ...] = ()
        for _, turns in completed_turn_blocks(messages):
            for turn in turns:
                assistant_payload = getattr(turn.assistant, "payload", {}) or {}
                if str(assistant_payload.get("learning_record_id") or "") in suppressed_records:
                    continue
                question = str(getattr(turn.user, "content", "") or "").strip()
                answer = str(getattr(turn.assistant, "content", "") or "").strip()
                if question and answer:
                    web_items = [
                        {
                            "title": str(item.get("title") or "网页")[:240],
                            "url": str(item.get("url") or "")[:2048],
                            "source_message_id": str(getattr(turn.assistant, "id", "") or ""),
                        }
                        for item in list(assistant_payload.get("citations") or [])[:10]
                        if isinstance(item, dict)
                        and item.get("source_type") == "web"
                    ]
                    if web_items:
                        web_references = tuple(web_items)
                    quiz_items = [
                        item for item in list(assistant_payload.get("artifacts") or [])
                        if isinstance(item, dict) and item.get("type") == "quiz" and item.get("id")
                    ]
                    if quiz_items:
                        quiz_reference = {
                            "id": str(quiz_items[-1]["id"])[:64],
                            "source_message_id": str(getattr(turn.assistant, "id", "") or ""),
                        }
                    material_items: dict[str, dict[str, Any]] = {}
                    for item in list(assistant_payload.get("artifacts") or [])[:10]:
                        if isinstance(item, dict) and item.get("type") == "material" and item.get("id"):
                            material_id = str(item["id"])
                            material_items[material_id] = {
                                "id": material_id, "title": str(item.get("title") or "课程资料")[:240],
                                "chunk_ids": [],
                                "source_message_id": str(getattr(turn.assistant, "id", "") or ""),
                            }
                    for item in list(assistant_payload.get("citations") or [])[:10]:
                        if not isinstance(item, dict) or item.get("source_type") != "document" or not item.get("source_id"):
                            continue
                        material_id = str(item["source_id"])
                        target = material_items.setdefault(material_id, {
                            "id": material_id, "title": str(item.get("title") or "课程资料")[:240],
                            "chunk_ids": [],
                            "source_message_id": str(getattr(turn.assistant, "id", "") or ""),
                        })
                        if item.get("chunk_id") and str(item["chunk_id"]) not in target["chunk_ids"]:
                            target["chunk_ids"].append(str(item["chunk_id"]))
                    if material_items:
                        material_references = tuple(material_items.values())
                    resource_items = [
                        {
                            "id": str(item.get("resource_id") or item.get("id"))[:64],
                            "title": str(item.get("title") or "学习资源")[:240],
                            "resource_type": str(item.get("resource_type") or item.get("subtype") or "")[:64],
                            "source_message_id": str(getattr(turn.assistant, "id", "") or ""),
                        }
                        for item in list(assistant_payload.get("artifacts") or [])[:10]
                        if isinstance(item, dict)
                        and item.get("type") == "resource"
                        and (item.get("resource_id") or item.get("id"))
                    ]
                    if resource_items:
                        resource_references = tuple(resource_items)
                    active_constraints = apply_session_changes(
                        active_constraints, text=question, source=turn.user,
                    )
                    completed.extend((("user", question), ("assistant", answer)))
        recent = completed[-12:]
        older_questions = [content[:80] for role, content in completed[:-12] if role == "user"]
        # Keep the opening goal and recent older requests within a fixed input budget.
        selected = list(dict.fromkeys(older_questions[:4] + older_questions[-10:]))
        while len("；".join(selected)) > 1200 and len(selected) > 1:
            selected.pop(4 if len(selected) > 5 else -1)
        last_question = next((content for role, content in reversed(recent) if role == "user"), None)
        return ConversationContext(
            history=tuple(recent), last_question=last_question,
            older_user_requests=tuple(selected),
            summary=summary,
            summary_version=summary_version,
            active_constraints=active_constraints,
            web_references=web_references,
            quiz_reference=quiz_reference,
            material_references=material_references,
            resource_references=resource_references,
        )

    async def _replay_session_constraints(
        self, *, conversation_id: UUID, before_sequence: int,
        suppressed_records: set[str],
    ) -> dict[str, dict[str, Any]]:
        # Rare path for old projections or queued tasks whose snapshot predates
        # the current projection. Re-read originals instead of adopting future state.
        rows = []
        cursor = 0
        while cursor < before_sequence:
            page = await self.conversations.list_messages_after_sequence(
                conversation_id, cursor, limit=120,
            )
            selected = [item for item in page if int(getattr(item, "sequence_no", 0)) < before_sequence]
            rows.extend(selected)
            if not page or len(selected) < len(page):
                break
            next_cursor = int(getattr(page[-1], "sequence_no", cursor))
            if next_cursor <= cursor:
                break
            cursor = next_cursor
        active: dict[str, dict[str, Any]] = {}
        for _, turns in completed_turn_blocks(rows):
            for turn in turns:
                assistant_payload = getattr(turn.assistant, "payload", {}) or {}
                if str(assistant_payload.get("learning_record_id") or "") in suppressed_records:
                    continue
                active = apply_session_changes(
                    active,
                    text=str(getattr(turn.user, "content", "") or ""),
                    source=turn.user,
                )
        return active
