from __future__ import annotations

import json
import logging
import re
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm import ChatMessage, get_llm_provider
from app.services.prompt_service import PromptService

logger = logging.getLogger(__name__)

COMMON_CANONICAL_NAMES = {
    "链栈": "链式栈",
    "栈的链式存储": "链式栈",
    "链队列": "链式队列",
    "队列的链式存储": "链式队列",
    "栈的顺序存储": "顺序栈",
    "队列的顺序存储": "顺序队列",
}


class KnowledgeCandidate(BaseModel):
    raw_name: str
    description: str = ""
    chapter: str | None = None
    source_chunk_ids: list[UUID] = Field(default_factory=list)
    source_order: int = 0


class NormalizedKnowledgeItem(BaseModel):
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    chapter: str | None = None
    parent_name: str | None = None
    description: str = ""
    difficulty: str | None = None
    importance: str | None = None
    sort_order: int = 0
    source_chunk_ids: list[UUID] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)
    decision_reason: str = ""


class RejectedKnowledgeItem(BaseModel):
    raw_name: str
    reason: str


class KnowledgeNormalizationOutput(BaseModel):
    items: list[NormalizedKnowledgeItem] = Field(default_factory=list)
    rejected: list[RejectedKnowledgeItem] = Field(default_factory=list)


class KnowledgeNormalizationResult(BaseModel):
    candidate_count: int
    merged_count: int
    rejected_count: int
    kept_count: int
    used_llm: bool
    fallback_reason: str | None = None
    items: list[NormalizedKnowledgeItem] = Field(default_factory=list)
    rejected: list[RejectedKnowledgeItem] = Field(default_factory=list)


class KnowledgeNormalizationService:
    def __init__(self, db: AsyncSession | None) -> None:
        self.db = db
        self.prompts = PromptService(db) if db is not None else None

    def clean_candidate_name(self, name: str) -> str:
        cleaned = re.sub(r"[*_`#>]+", "", name).strip()
        cleaned = re.sub(
            r"^\s*(?:第[一二三四五六七八九十百千\d]+[章节篇]\s*|"
            r"\d+(?:\.\d+)*[.、）)]?\s*|[（(][一二三四五六七八九十\d]+[）)]\s*)",
            "",
            cleaned,
        )
        return cleaned.strip(" \t\r\n:：;；,，.。-—")

    def is_valid_name(self, name: str) -> bool:
        cleaned = self.clean_candidate_name(name)
        if not 2 <= len(cleaned) <= 32:
            return False
        if re.fullmatch(r"[\d\W_]+", cleaned):
            return False
        if cleaned.startswith(("与", "和", "及", "或", "而", "其中", "通过", "按", "点击", "建议")):
            return False
        if any(marker in cleaned for marker in ("。", "；", "，", "：", ":", "→", "->")):
            return False
        if re.search(r"\bO\s*\([^)]+\)", cleaned, re.IGNORECASE):
            return False
        if len(cleaned.split()) > 5:
            return False
        return True

    async def normalize(
        self,
        *,
        candidates: list[KnowledgeCandidate],
        course_id: UUID,
        owner_id: UUID,
        min_items: int = 15,
        max_items: int = 30,
    ) -> KnowledgeNormalizationResult:
        valid, rejected = self._clean_candidates(candidates)
        if not valid:
            return KnowledgeNormalizationResult(
                candidate_count=len(candidates),
                merged_count=0,
                rejected_count=len(rejected),
                kept_count=0,
                used_llm=False,
                fallback_reason="没有通过确定性校验的候选知识点",
                rejected=rejected,
            )

        if self.db is not None:
            try:
                output = await self._normalize_with_llm(
                    valid,
                    course_id=course_id,
                    owner_id=owner_id,
                    min_items=min_items,
                    max_items=max_items,
                )
                items = self._validate_llm_items(output.items, valid, max_items=max_items)
                if items:
                    return self._build_result(
                        candidates=candidates,
                        items=items,
                        rejected=[*rejected, *output.rejected],
                        used_llm=True,
                    )
            except Exception as exc:
                logger.warning("知识点 LLM 归一化失败，使用规则整理: %s", exc)
                fallback_reason = str(exc)
            else:
                fallback_reason = "LLM 未返回可验证的知识点"
        else:
            fallback_reason = "未提供数据库上下文，使用规则整理"

        items, rule_rejected = self._normalize_by_rules(valid, max_items=max_items)
        return self._build_result(
            candidates=candidates,
            items=items,
            rejected=[*rejected, *rule_rejected],
            used_llm=False,
            fallback_reason=fallback_reason,
        )

    def _clean_candidates(
        self, candidates: list[KnowledgeCandidate]
    ) -> tuple[list[KnowledgeCandidate], list[RejectedKnowledgeItem]]:
        valid: list[KnowledgeCandidate] = []
        rejected: list[RejectedKnowledgeItem] = []
        for candidate in candidates:
            name = self.clean_candidate_name(candidate.raw_name)
            if not candidate.source_chunk_ids:
                rejected.append(RejectedKnowledgeItem(raw_name=candidate.raw_name, reason="缺少来源切片"))
                continue
            if not self.is_valid_name(name):
                rejected.append(RejectedKnowledgeItem(raw_name=candidate.raw_name, reason="名称不是规范课程概念"))
                continue
            valid.append(candidate.model_copy(update={"raw_name": name}))
        return valid, rejected

    async def _normalize_with_llm(
        self,
        candidates: list[KnowledgeCandidate],
        *,
        course_id: UUID,
        owner_id: UUID,
        min_items: int,
        max_items: int,
    ) -> KnowledgeNormalizationOutput:
        provider = get_llm_provider(db=self.db, user_id=owner_id, course_id=course_id)
        payload = [candidate.model_dump(mode="json") for candidate in candidates]
        rendered = await self.prompts.render_prompt(  # type: ignore[union-attr]
            agent_name="KnowledgeAgent",
            scene="knowledge.normalize",
            params={
                "min_items": min_items,
                "max_items": max_items,
                "candidates": json.dumps(payload, ensure_ascii=False),
            },
        )
        return await provider.structured_chat(
            [ChatMessage(role="user", content=rendered.content)],
            KnowledgeNormalizationOutput,
            temperature=0.2,
            max_tokens=4096,
            user_id=owner_id,
            course_id=course_id,
            prompt_version_id=rendered.prompt_version_id,
        )

    def _validate_llm_items(
        self,
        items: list[NormalizedKnowledgeItem],
        candidates: list[KnowledgeCandidate],
        *,
        max_items: int,
    ) -> list[NormalizedKnowledgeItem]:
        allowed_chunk_ids = {chunk_id for candidate in candidates for chunk_id in candidate.source_chunk_ids}
        validated: list[NormalizedKnowledgeItem] = []
        seen: set[str] = set()
        for item in items:
            name = self.clean_candidate_name(item.canonical_name)
            source_ids = list(dict.fromkeys(item.source_chunk_ids))
            if (
                not self.is_valid_name(name)
                or name.casefold() in seen
                or not source_ids
                or any(chunk_id not in allowed_chunk_ids for chunk_id in source_ids)
            ):
                continue
            seen.add(name.casefold())
            validated.append(item.model_copy(update={"canonical_name": name, "source_chunk_ids": source_ids}))
        return self._rank_items(validated)[:max_items]

    def _normalize_by_rules(
        self, candidates: list[KnowledgeCandidate], *, max_items: int
    ) -> tuple[list[NormalizedKnowledgeItem], list[RejectedKnowledgeItem]]:
        by_name: dict[str, NormalizedKnowledgeItem] = {}
        rejected: list[RejectedKnowledgeItem] = []
        for candidate in candidates:
            canonical_name = COMMON_CANONICAL_NAMES.get(candidate.raw_name, candidate.raw_name)
            key = canonical_name.casefold()
            existing = by_name.get(key)
            if existing is not None:
                existing.source_chunk_ids = list(
                    dict.fromkeys([*existing.source_chunk_ids, *candidate.source_chunk_ids])
                )
                if candidate.raw_name != canonical_name and candidate.raw_name not in existing.aliases:
                    existing.aliases.append(candidate.raw_name)
                continue
            by_name[key] = NormalizedKnowledgeItem(
                canonical_name=canonical_name,
                aliases=[candidate.raw_name] if candidate.raw_name != canonical_name else [],
                chapter=candidate.chapter,
                description=candidate.description[:500],
                sort_order=candidate.source_order,
                source_chunk_ids=candidate.source_chunk_ids,
                confidence=0.6,
                decision_reason="规则清洗并按资料出现顺序整理",
            )

        ranked = self._rank_items(list(by_name.values()))
        for item in ranked[max_items:]:
            rejected.append(RejectedKnowledgeItem(raw_name=item.canonical_name, reason="超过单份资料知识点数量上限"))
        return ranked[:max_items], rejected

    def _rank_items(self, items: list[NormalizedKnowledgeItem]) -> list[NormalizedKnowledgeItem]:
        importance_rank = {"core": 0, "high": 0, "normal": 1, "medium": 1, "low": 2, None: 1}
        return sorted(
            items,
            key=lambda item: (
                importance_rank.get(item.importance, 1),
                -len(item.source_chunk_ids),
                -item.confidence,
                item.sort_order,
                item.canonical_name,
            ),
        )

    def _build_result(
        self,
        *,
        candidates: list[KnowledgeCandidate],
        items: list[NormalizedKnowledgeItem],
        rejected: list[RejectedKnowledgeItem],
        used_llm: bool,
        fallback_reason: str | None = None,
    ) -> KnowledgeNormalizationResult:
        merged_count = max(0, len(candidates) - len(rejected) - len(items))
        return KnowledgeNormalizationResult(
            candidate_count=len(candidates),
            merged_count=merged_count,
            rejected_count=len(rejected),
            kept_count=len(items),
            used_llm=used_llm,
            fallback_reason=fallback_reason,
            items=items,
            rejected=rejected,
        )
