from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.llm.embedding import get_embedding_provider


@dataclass
class SearchResult:
    chunk_id: UUID
    content: str
    score: float
    source_title: str | None
    page_no: int | None
    material_id: UUID


class VectorRetriever:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(
        self,
        course_id: UUID,
        query: str,
        user_id: UUID | None,
        top_k: int = 5,
        knowledge_id: UUID | None = None,
    ) -> list[SearchResult]:
        provider = get_embedding_provider()
        vectors = await provider.embed_texts([query])
        query_vec = vectors[0]

        # Check if any chunks have embeddings
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
        result = await self.db.execute(check_sql, {"course_id": str(course_id), **visibility_params})
        count = result.scalar()
        if not count:
            raise BusinessException(
                code=ErrorCode.VECTOR_SEARCH_FAILED,
                detail="该课程下尚无已生成向量的文档切片，请先执行 embed 操作",
                status_code=400,
            )

        if not await self._has_vector_extension():
            return await self._text_fallback_search(
                course_id=course_id,
                query=query,
                user_id=user_id,
                top_k=top_k,
                knowledge_id=knowledge_id,
            )

        # pgvector cosine distance search
        vec_literal = "[" + ",".join(str(v) for v in query_vec) + "]"

        conditions = [
            "dc.course_id = :course_id",
            "dc.embedding IS NOT NULL",
        ]
        params: dict = {
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

        where_clause = " AND ".join(conditions)

        search_sql = text(
            f"SELECT dc.id, dc.content, dc.source_title, dc.page_no, dc.material_id, "
            f"1 - (dc.embedding <=> CAST(:query_vec AS vector)) AS score "
            f"FROM document_chunks dc "
            f"JOIN course_materials cm ON cm.id = dc.material_id "
            f"WHERE {where_clause} "
            f"ORDER BY dc.embedding <=> CAST(:query_vec AS vector) "
            f"LIMIT :top_k"
        )

        try:
            rows = await self.db.execute(search_sql, params)
        except SQLAlchemyError as exc:
            if "vector" not in str(exc).lower():
                raise
            return await self._text_fallback_search(
                course_id=course_id,
                query=query,
                user_id=user_id,
                top_k=top_k,
                knowledge_id=knowledge_id,
            )
        return [
            SearchResult(
                chunk_id=row.id,
                content=row.content,
                score=float(row.score),
                source_title=row.source_title,
                page_no=row.page_no,
                material_id=row.material_id,
            )
            for row in rows
        ]

    async def _has_vector_extension(self) -> bool:
        result = await self.db.execute(
            text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
        )
        return bool(result.scalar())

    async def _text_fallback_search(
        self,
        *,
        course_id: UUID,
        query: str,
        user_id: UUID | None,
        top_k: int,
        knowledge_id: UUID | None,
    ) -> list[SearchResult]:
        terms = [term for term in query.replace("，", " ").replace("。", " ").split() if term]
        if not terms:
            terms = [query]

        visibility_clause, visibility_params = self._visibility_sql(
            course_id=course_id,
            user_id=user_id,
            alias="cm",
        )
        conditions = ["dc.course_id = :course_id"]
        params: dict[str, object] = {
            "course_id": str(course_id),
            "top_k": top_k,
            **visibility_params,
        }
        if visibility_clause:
            conditions.append(visibility_clause.removeprefix(" AND "))
        if knowledge_id is not None:
            conditions.append("dc.knowledge_id = :knowledge_id")
            params["knowledge_id"] = str(knowledge_id)

        score_parts: list[str] = []
        for index, term in enumerate(terms[:5]):
            key = f"term_{index}"
            params[key] = f"%{term}%"
            score_parts.append(f"CASE WHEN dc.content ILIKE :{key} THEN 1 ELSE 0 END")

        score_expr = " + ".join(score_parts) if score_parts else "0"
        where_clause = " AND ".join(conditions)

        fallback_sql = text(
            "SELECT dc.id, dc.content, dc.source_title, dc.page_no, dc.material_id, "
            f"({score_expr})::float AS score "
            "FROM document_chunks dc "
            "JOIN course_materials cm ON cm.id = dc.material_id "
            f"WHERE {where_clause} "
            "ORDER BY score DESC, dc.chunk_index ASC "
            "LIMIT :top_k"
        )
        rows = await self.db.execute(fallback_sql, params)
        return [
            SearchResult(
                chunk_id=row.id,
                content=row.content,
                score=float(row.score or 0),
                source_title=row.source_title,
                page_no=row.page_no,
                material_id=row.material_id,
            )
            for row in rows
        ]

    def _visibility_sql(
        self,
        *,
        course_id: UUID,
        user_id: UUID | None,
        alias: str,
    ) -> tuple[str, dict[str, object]]:
        if user_id is None:
            return "", {}
        return (
            f" AND ({alias}.uploaded_by = :user_id OR {alias}.uploaded_by = "
            "(SELECT owner_id FROM courses WHERE id = :course_id AND visibility = 'public_template'))",
            {"user_id": str(user_id)},
        )
