from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.wiki import WikiPage
from app.rag.evidence import EvidenceBundle, EvidenceItem, GraphContext
from app.rag.graph_retriever import GraphRetriever
from app.repositories.course_repository import CourseRepository
from app.repositories.wiki_repository import WikiRepository


class EvidenceRetrievalService:
    VECTOR_STRONG = 0.55
    VECTOR_WITH_TITLE = 0.45
    KEYWORD_STRONG = 1.0
    MAX_EVIDENCE = 5
    MAX_PER_SOURCE = 2

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.graph = GraphRetriever(db)
        self.courses = CourseRepository(db)
        self.wiki = WikiRepository(db)

    async def retrieve(
        self,
        *,
        course_id: UUID,
        user_id: UUID,
        question: str,
        top_k: int,
        knowledge_id: UUID | None,
        wiki_page_id: UUID | None,
        use_rag: bool,
        use_wiki: bool,
        is_admin: bool = False,
    ) -> EvidenceBundle:
        graph_payload: dict[str, Any] = {"items": [], "graph_context": {}}
        if use_rag:
            graph_payload = await self.graph.search(
                course_id=course_id,
                query=question,
                user_id=user_id,
                top_k=max(top_k * 2, 10),
                expand_hops=1,
                knowledge_id=knowledge_id,
            )
        wiki_pages = []
        if use_wiki:
            wiki_pages = await self._load_wiki_pages(
                course_id=course_id,
                user_id=user_id,
                question=question,
                knowledge_id=knowledge_id,
                wiki_page_id=wiki_page_id,
                is_admin=is_admin,
            )

        document_items = list(graph_payload.get("items") or [])
        candidate_count = len(document_items) + len(wiki_pages)
        terms = self._question_terms(question)
        document_evidence: list[EvidenceItem] = []
        source_counts: dict[UUID, int] = defaultdict(int)
        for item in document_items:
            material_id = self._parse_uuid(item.get("material_id"))
            chunk_id = self._parse_uuid(item.get("chunk_id"))
            if material_id is None or chunk_id is None:
                continue
            if not self._accept_document(item, terms):
                continue
            if source_counts[material_id] >= self.MAX_PER_SOURCE:
                continue
            source_counts[material_id] += 1
            meta = item.get("extra_meta") if isinstance(item.get("extra_meta"), dict) else {}
            document_evidence.append(
                EvidenceItem(
                    citation_key="",
                    source_type="document",
                    source_id=material_id,
                    chunk_id=chunk_id,
                    knowledge_id=self._parse_uuid(meta.get("knowledge_id")),
                    title=str(item.get("source_title") or "课程资料"),
                    quote=str(item.get("content") or "")[:1200],
                    page_no=item.get("page_no") if isinstance(item.get("page_no"), int) else None,
                    retrieval_mode=str(item.get("retrieval_mode") or "hybrid"),
                    vector_score=float(item.get("vector_score") or 0.0),
                    keyword_score=float(item.get("keyword_score") or 0.0),
                    rerank_score=float(item.get("rerank_score") or item.get("score") or 0.0),
                    confidence=self._confidence(item),
                )
            )

        explicit_wiki_evidence: list[EvidenceItem] = []
        automatic_wiki_evidence: list[EvidenceItem] = []
        seen_page_ids: set[UUID] = set()
        for page in wiki_pages:
            if page.id in seen_page_ids:
                continue
            seen_page_ids.add(page.id)
            is_explicit = page.id == wiki_page_id
            target = explicit_wiki_evidence if is_explicit else automatic_wiki_evidence
            target.append(self._wiki_evidence(page, is_explicit=is_explicit))

        limit = min(self.MAX_EVIDENCE, max(top_k, 0))
        evidence = explicit_wiki_evidence + document_evidence + automatic_wiki_evidence
        selected = evidence[:limit]
        selected = [
            replace(item, citation_key=f"S{index}")
            for index, item in enumerate(selected, start=1)
        ]
        return EvidenceBundle(
            evidence=selected,
            graph_context=self._graph_context(graph_payload.get("graph_context")),
            candidate_count=candidate_count,
        )

    async def _load_wiki_pages(
        self,
        *,
        course_id: UUID,
        user_id: UUID,
        question: str,
        knowledge_id: UUID | None,
        wiki_page_id: UUID | None,
        is_admin: bool = False,
    ) -> list[WikiPage]:
        course = await self.courses.get_by_id(course_id)
        public_owner_id = None
        if (
            course is not None
            and course.visibility == "public_template"
            and course.status == "active"
        ):
            public_owner_id = course.owner_id

        allowed_owner_ids = {user_id}
        if public_owner_id is not None:
            allowed_owner_ids.add(public_owner_id)

        explicit_page: WikiPage | None = None
        if wiki_page_id is not None:
            explicit_page = await self.wiki.get_by_id_simple(wiki_page_id)
            self._require_readable_explicit_page(
                explicit_page,
                course_id=course_id,
                allowed_owner_ids=allowed_owner_ids,
                is_admin=is_admin,
            )
            assert explicit_page is not None
            if knowledge_id is not None and explicit_page.knowledge_id != knowledge_id:
                return []

        owner_ids = [user_id]
        if public_owner_id is not None and public_owner_id != user_id:
            owner_ids.append(public_owner_id)
        pages, _ = await self.wiki.list_by_owners(owner_ids, course_id, page_size=20)
        terms = [term.lower() for term in self._question_terms(question) if len(term) >= 2]
        scored: list[tuple[int, WikiPage]] = []
        seen_page_ids = {explicit_page.id} if explicit_page is not None else set()
        for page in pages:
            if page.id in seen_page_ids:
                continue
            if not self._is_readable_wiki_page(
                page,
                course_id=course_id,
                allowed_owner_ids=allowed_owner_ids,
                is_admin=is_admin,
            ):
                continue
            if knowledge_id is not None and page.knowledge_id != knowledge_id:
                continue
            haystack = f"{page.title}\n{page.summary or ''}\n{page.content}".lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                scored.append((score, page))
                seen_page_ids.add(page.id)
        scored.sort(key=lambda item: item[0], reverse=True)
        automatic_pages = [page for _, page in scored[:3]]
        return ([explicit_page] if explicit_page is not None else []) + automatic_pages

    def _is_readable_wiki_page(
        self,
        page: WikiPage | None,
        *,
        course_id: UUID,
        allowed_owner_ids: set[UUID],
        is_admin: bool = False,
    ) -> bool:
        return (
            page is not None
            and page.course_id == course_id
            and page.status == "active"
            and (is_admin or page.owner_id in allowed_owner_ids)
        )

    async def require_readable_wiki_page(
        self,
        *,
        course_id: UUID,
        user_id: UUID,
        wiki_page_id: UUID,
        is_admin: bool = False,
    ) -> WikiPage:
        course = await self.courses.get_by_id(course_id)
        allowed_owner_ids = {user_id}
        if (
            course is not None
            and course.visibility == "public_template"
            and course.status == "active"
        ):
            allowed_owner_ids.add(course.owner_id)
        page = await self.wiki.get_by_id_simple(wiki_page_id)
        self._require_readable_explicit_page(
            page,
            course_id=course_id,
            allowed_owner_ids=allowed_owner_ids,
            is_admin=is_admin,
        )
        assert page is not None
        return page

    def _require_readable_explicit_page(
        self,
        page: WikiPage | None,
        *,
        course_id: UUID,
        allowed_owner_ids: set[UUID],
        is_admin: bool,
    ) -> None:
        if page is not None and page.course_id == course_id and page.status == "archived":
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="已归档的 Wiki 页面不可用于问答",
                status_code=400,
            )
        if not self._is_readable_wiki_page(
            page,
            course_id=course_id,
            allowed_owner_ids=allowed_owner_ids,
            is_admin=is_admin,
        ):
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="Wiki 页面不存在",
                status_code=404,
            )

    def _wiki_evidence(self, page: WikiPage, *, is_explicit: bool) -> EvidenceItem:
        return EvidenceItem(
            citation_key="",
            source_type="wiki",
            source_id=page.id,
            page_id=page.id,
            knowledge_id=page.knowledge_id,
            title=page.title,
            quote=str(page.summary or page.content[:1200] or "Wiki 页面"),
            retrieval_mode="wiki_explicit" if is_explicit else "wiki_match",
            rerank_score=1.0 if is_explicit else 0.0,
            confidence="strong" if is_explicit else "acceptable",
        )

    def _accept_document(self, item: dict[str, Any], terms: list[str]) -> bool:
        vector = float(item.get("vector_score") or 0.0)
        keyword = float(item.get("keyword_score") or 0.0)
        title = str(item.get("source_title") or "").lower()
        title_hit = any(term.lower() in title for term in terms)
        return keyword >= self.KEYWORD_STRONG or vector >= self.VECTOR_STRONG or (
            title_hit and vector >= self.VECTOR_WITH_TITLE
        )

    def _confidence(self, item: dict[str, Any]) -> Literal["strong", "acceptable"]:
        if float(item.get("keyword_score") or 0.0) >= self.KEYWORD_STRONG:
            return "strong"
        if float(item.get("vector_score") or 0.0) >= self.VECTOR_STRONG:
            return "strong"
        return "acceptable"

    def _question_terms(self, question: str) -> list[str]:
        from app.rag.hybrid_retriever import _query_terms

        return _query_terms(question)

    def _graph_context(self, value: object) -> GraphContext:
        payload = value if isinstance(value, dict) else {}
        return GraphContext(
            seed_knowledge_ids=self._uuid_list(payload.get("seed_knowledge_ids")),
            expanded_knowledge_ids=self._uuid_list(payload.get("expanded_knowledge_ids")),
            relation_paths=list(payload.get("relation_paths") or []),
        )

    def _uuid_list(self, values: object) -> list[UUID]:
        if not isinstance(values, list):
            return []
        return [parsed for value in values if (parsed := self._parse_uuid(value)) is not None]

    def _parse_uuid(self, value: object) -> UUID | None:
        if isinstance(value, UUID):
            return value
        if isinstance(value, str):
            try:
                return UUID(value)
            except ValueError:
                return None
        return None
