from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.embedding import get_embedding_provider


logger = logging.getLogger(__name__)


@dataclass
class RetrievalCandidate:
    chunk_id: UUID
    material_id: UUID
    content: str
    source_title: str | None
    page_no: int | None
    vector_score: float = 0.0
    keyword_score: float = 0.0
    vector_rank: int | None = None
    keyword_rank: int | None = None
    extra_meta: dict[str, Any] = field(default_factory=dict)
    retrieval_mode: str = "hybrid"
    rerank_score: float = 0.0

    @property
    def score(self) -> float:
        return self.rerank_score or max(self.vector_score, self.keyword_score)


class HybridRetriever:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(
        self,
        course_id: UUID,
        query: str,
        user_id: UUID | None,
        top_k: int = 5,
        knowledge_id: UUID | None = None,
    ) -> list[RetrievalCandidate]:
        candidate_k = max(top_k * 8, 30)
        try:
            vector_candidates = await self._vector_search(
                course_id=course_id,
                query=query,
                user_id=user_id,
                top_k=candidate_k,
                knowledge_id=knowledge_id,
            )
        except httpx.TransportError as exc:
            logger.warning(
                "Vector retrieval unavailable; using keyword fallback: %s", exc
            )
            vector_candidates = []
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code != 429 and not 500 <= status_code <= 599:
                raise
            logger.warning(
                "Vector retrieval unavailable; using keyword fallback: %s", exc
            )
            vector_candidates = []
        except SQLAlchemyError as exc:
            if not _is_pgvector_unavailable(exc):
                raise
            logger.warning(
                "Vector retrieval unavailable; using keyword fallback: %s", exc
            )
            vector_candidates = []
        except RuntimeError as exc:
            if not _is_embedding_unavailable_runtime(exc):
                raise
            logger.warning(
                "Vector retrieval unavailable; using keyword fallback: %s", exc
            )
            vector_candidates = []
        keyword_candidates = await self._keyword_search(
            course_id=course_id,
            query=query,
            user_id=user_id,
            top_k=candidate_k,
            knowledge_id=knowledge_id,
        )
        return fuse_and_rerank_results(query, vector_candidates + keyword_candidates, top_k=top_k)

    async def _vector_search(
        self,
        *,
        course_id: UUID,
        query: str,
        user_id: UUID | None,
        top_k: int,
        knowledge_id: UUID | None,
    ) -> list[RetrievalCandidate]:
        if not await self._has_vector_extension():
            return []

        visibility_clause, visibility_params = self._visibility_sql(
            course_id=course_id,
            user_id=user_id,
            alias="cm",
        )
        check_sql = text(
            "SELECT COUNT(*) FROM document_chunks dc "
            "JOIN course_materials cm ON cm.id = dc.material_id "
            f"WHERE dc.course_id = :course_id AND dc.embedding IS NOT NULL {visibility_clause}"
        )
        count = (
            await self.db.execute(check_sql, {"course_id": str(course_id), **visibility_params})
        ).scalar()
        if not count:
            return []

        provider = get_embedding_provider()
        query_vec = (await provider.embed_texts([query]))[0]
        vec_literal = "[" + ",".join(str(v) for v in query_vec) + "]"
        conditions = ["dc.course_id = :course_id", "dc.embedding IS NOT NULL"]
        params: dict[str, object] = {
            "course_id": str(course_id),
            "top_k": top_k,
            "query_vec": vec_literal,
            **visibility_params,
        }
        if visibility_clause:
            conditions.append(visibility_clause.removeprefix(" AND "))
        if knowledge_id is not None:
            conditions.append("dc.knowledge_id = :knowledge_id")
            params["knowledge_id"] = str(knowledge_id)

        sql = text(
            "SELECT dc.id, dc.content, dc.source_title, dc.page_no, dc.material_id, dc.extra_meta, "
            "1 - (dc.embedding <=> CAST(:query_vec AS vector)) AS score "
            "FROM document_chunks dc "
            "JOIN course_materials cm ON cm.id = dc.material_id "
            f"WHERE {' AND '.join(conditions)} "
            "ORDER BY dc.embedding <=> CAST(:query_vec AS vector) "
            "LIMIT :top_k"
        )
        rows = list((await self.db.execute(sql, params)).all())

        return [
            RetrievalCandidate(
                chunk_id=row.id,
                material_id=row.material_id,
                content=row.content,
                source_title=row.source_title,
                page_no=row.page_no,
                vector_score=float(row.score or 0.0),
                vector_rank=index + 1,
                extra_meta=dict(row.extra_meta or {}),
                retrieval_mode="vector",
            )
            for index, row in enumerate(rows)
        ]

    async def _keyword_search(
        self,
        *,
        course_id: UUID,
        query: str,
        user_id: UUID | None,
        top_k: int,
        knowledge_id: UUID | None,
    ) -> list[RetrievalCandidate]:
        terms = _query_terms(query)
        visibility_clause, visibility_params = self._visibility_sql(
            course_id=course_id,
            user_id=user_id,
            alias="cm",
        )
        conditions = ["dc.course_id = :course_id"]
        params: dict[str, object] = {
            "course_id": str(course_id),
            "top_k": top_k,
            "query_like": f"%{query}%",
            **visibility_params,
        }
        if visibility_clause:
            conditions.append(visibility_clause.removeprefix(" AND "))
        if knowledge_id is not None:
            conditions.append("dc.knowledge_id = :knowledge_id")
            params["knowledge_id"] = str(knowledge_id)

        term_conditions: list[str] = ["dc.content ILIKE :query_like"]
        score_parts: list[str] = ["CASE WHEN dc.content ILIKE :query_like THEN 3 ELSE 0 END"]
        for index, term in enumerate(terms[:8]):
            key = f"term_{index}"
            params[key] = f"%{term}%"
            term_conditions.append(f"dc.content ILIKE :{key}")
            term_conditions.append(f"dc.extra_meta::text ILIKE :{key}")
            score_parts.append(f"CASE WHEN dc.content ILIKE :{key} THEN 1 ELSE 0 END")
            score_parts.append(f"CASE WHEN dc.extra_meta::text ILIKE :{key} THEN 0.5 ELSE 0 END")

        conditions.append("(" + " OR ".join(term_conditions) + ")")
        score_expr = " + ".join(score_parts)
        sql = text(
            "SELECT dc.id, dc.content, dc.source_title, dc.page_no, dc.material_id, dc.extra_meta, "
            f"({score_expr})::float AS score "
            "FROM document_chunks dc "
            "JOIN course_materials cm ON cm.id = dc.material_id "
            f"WHERE {' AND '.join(conditions)} "
            "ORDER BY score DESC, dc.chunk_index ASC "
            "LIMIT :top_k"
        )
        rows = list((await self.db.execute(sql, params)).all())
        return [
            RetrievalCandidate(
                chunk_id=row.id,
                material_id=row.material_id,
                content=row.content,
                source_title=row.source_title,
                page_no=row.page_no,
                keyword_score=float(row.score or 0.0),
                keyword_rank=index + 1,
                extra_meta=dict(row.extra_meta or {}),
                retrieval_mode="keyword",
            )
            for index, row in enumerate(rows)
        ]

    async def _has_vector_extension(self) -> bool:
        result = await self.db.execute(
            text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
        )
        return bool(result.scalar())

    def _visibility_sql(
        self,
        *,
        course_id: UUID,
        user_id: UUID | None,
        alias: str,
    ) -> tuple[str, dict[str, object]]:
        # course_id 已在调用方限定；user_id 仅保留参数兼容，不再过滤上传者。
        return "", {}


def fuse_and_rerank_results(
    query: str,
    candidates: list[RetrievalCandidate],
    *,
    top_k: int,
) -> list[RetrievalCandidate]:
    merged: dict[UUID, RetrievalCandidate] = {}
    for item in candidates:
        current = merged.get(item.chunk_id)
        if current is None:
            merged[item.chunk_id] = item
            continue
        current.vector_score = max(current.vector_score, item.vector_score)
        current.keyword_score = max(current.keyword_score, item.keyword_score)
        current.vector_rank = _min_rank(current.vector_rank, item.vector_rank)
        current.keyword_rank = _min_rank(current.keyword_rank, item.keyword_rank)
        current.extra_meta = {**item.extra_meta, **current.extra_meta}
        current.retrieval_mode = "hybrid"

    for item in merged.values():
        item.retrieval_mode = _retrieval_mode(item)
        item.rerank_score = _rerank_score(query, item)
    ranked = sorted(merged.values(), key=lambda result: result.rerank_score, reverse=True)
    return _diversify_sources(ranked, top_k)


def _rerank_score(query: str, candidate: RetrievalCandidate) -> float:
    score = 0.0
    if candidate.vector_rank is not None:
        score += 0.65 / (60 + candidate.vector_rank)
        score += max(candidate.vector_score, 0.0) * 0.2
    if candidate.keyword_rank is not None:
        score += 0.25 / (60 + candidate.keyword_rank)
        score += min(candidate.keyword_score / 5, 1.0) * 0.25

    terms = _query_terms(query)
    heading_text = _heading_text(candidate.extra_meta).lower()
    content_lower = candidate.content.lower()
    heading_hits = sum(1 for term in terms if term.lower() in heading_text)
    content_hits = sum(1 for term in terms if term.lower() in content_lower)
    score += min(heading_hits, 3) * 0.04
    score += min(content_hits, 5) * 0.015

    chunk_type = str(candidate.extra_meta.get("chunk_type") or "")
    if chunk_type in {"definition", "complexity", "example", "code"}:
        score += 0.08
    source_quality = candidate.extra_meta.get("source_quality_score")
    if isinstance(source_quality, int | float):
        score += min(max(float(source_quality), 0.0), 100.0) / 5000
    length = len(candidate.content)
    if length < 60:
        score -= 0.04
    elif length > 2500:
        score -= 0.03
    return round(score, 6)


def _query_terms(query: str) -> list[str]:
    separators = " ，。！？；：,.!?;:\n\t()（）[]【】"
    terms: list[str] = []
    current = ""
    for char in query:
        if char in separators:
            if current:
                terms.append(current)
                current = ""
        else:
            current += char
    if current:
        terms.append(current)

    domain_terms = [
        "哈希表",
        "冲突解决",
        "链地址法",
        "开放定址",
        "栈",
        "队列",
        "二叉树",
        "堆",
        "图",
        "邻接表",
        "BFS",
        "DFS",
        "排序",
        "查找",
        "复杂度",
    ]
    for term in domain_terms:
        if term.lower() in query.lower():
            terms.append(term)

    generated_count = 0
    for segment in list(terms):
        for chinese_run in re.findall(r"[\u4e00-\u9fff]+", segment):
            for width in range(2, 5):
                for start in range(0, len(chinese_run) - width + 1):
                    window = chinese_run[start : start + width]
                    if window not in terms:
                        terms.append(window)
                        generated_count += 1
                    if generated_count >= 24:
                        break
                if generated_count >= 24:
                    break
            if generated_count >= 24:
                break
        if generated_count >= 24:
            break
    return list(dict.fromkeys(term.strip() for term in terms if len(term.strip()) >= 1))


def _heading_text(extra_meta: dict[str, Any]) -> str:
    heading = extra_meta.get("heading_path")
    if isinstance(heading, list):
        return " ".join(str(item) for item in heading)
    return str(heading or "")


def _is_pgvector_unavailable(exc: SQLAlchemyError) -> bool:
    message = str(exc).lower()
    pgvector_markers = (
        'type "vector" does not exist',
        "type vector does not exist",
        'extension "vector" is not available',
        'extension "vector" does not exist',
        'extension "vector" is not installed',
        "extension vector is not available",
        "extension vector does not exist",
        "extension vector is not installed",
    )
    return any(marker in message for marker in pgvector_markers)


def _is_embedding_unavailable_runtime(exc: RuntimeError) -> bool:
    message = str(exc).lower()
    unavailable_markers = (
        "vector unavailable",
        "embedding unavailable",
        "embedding provider unavailable",
        "real embedding provider is required",
        "sentence-transformers is required",
    )
    return any(marker in message for marker in unavailable_markers)


def _min_rank(left: int | None, right: int | None) -> int | None:
    if left is None:
        return right
    if right is None:
        return left
    return min(left, right)


def _retrieval_mode(candidate: RetrievalCandidate) -> str:
    if candidate.vector_rank is not None and candidate.keyword_rank is not None:
        return "hybrid"
    if candidate.vector_rank is not None:
        return "vector"
    return "keyword"


def _diversify_sources(
    ranked: list[RetrievalCandidate],
    top_k: int,
) -> list[RetrievalCandidate]:
    if top_k <= 0:
        return []
    per_source_limit = max(2, top_k // 2)
    selected: list[RetrievalCandidate] = []
    source_counts: dict[str, int] = {}
    deferred: list[RetrievalCandidate] = []
    for item in ranked:
        source_id = str(item.extra_meta.get("source_id") or item.material_id)
        if source_counts.get(source_id, 0) < per_source_limit:
            selected.append(item)
            source_counts[source_id] = source_counts.get(source_id, 0) + 1
        else:
            deferred.append(item)
        if len(selected) >= top_k:
            break
    if len(selected) < top_k:
        selected.extend(deferred[: top_k - len(selected)])
    return selected[:top_k]
