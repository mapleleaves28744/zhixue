from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.knowledge import KnowledgePoint
from app.models.material import CourseMaterial
from app.models.user import User
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.course_repository import CourseRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.material_repository import MaterialRepository
from app.services.knowledge_normalization_service import (
    KnowledgeCandidate,
    KnowledgeNormalizationResult,
    KnowledgeNormalizationService,
)

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeExtractionResult:
    points: list[KnowledgePoint]
    relations_created: int
    normalization: KnowledgeNormalizationResult


class KnowledgeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.materials = MaterialRepository(db)
        self.courses = CourseRepository(db)
        self.chunks = ChunkRepository(db)
        self.knowledge = KnowledgeRepository(db)
        self.normalizer = KnowledgeNormalizationService(db)

    async def extract_from_material(
        self,
        material_id: UUID,
        *,
        current_user: User | None = None,
    ) -> KnowledgeExtractionResult:
        material = await self.materials.get_by_id(material_id)
        if material is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="资料不存在",
                status_code=404,
            )

        chunks = await self.chunks.list_by_material(material_id)
        if not chunks:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="资料尚未切片，请先执行 chunk 操作",
                status_code=400,
            )

        full_text = "\n\n".join(c.content for c in chunks)
        candidates = self._extract_candidates_from_chunks(chunks)

        course = await self.courses.get_by_id(material.course_id)
        if course is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="课程不存在",
                status_code=404,
            )
        scope = (
            "public"
            if course.visibility == "public_template" and material.uploaded_by == course.owner_id
            else "personal"
        )

        normalization = await self.normalizer.normalize(
            candidates=candidates,
            course_id=material.course_id,
            owner_id=material.uploaded_by,
        )
        if not normalization.items:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="当前资料未整理出合格知识点，请检查资料结构和内容",
                status_code=400,
            )

        extracted = [
            {
                "name": item.canonical_name,
                "chapter": item.chapter,
                "description": item.description,
                "difficulty": item.difficulty,
                "importance": item.importance,
                "sort_order": item.sort_order,
            }
            for item in normalization.items
        ]
        points, new_count = await self.knowledge.create_batch_if_not_exists(
            course_id=material.course_id,
            owner_id=material.uploaded_by,
            scope=scope,
            items=extracted,
        )
        _ = new_count
        point_by_name = {point.name.casefold(): point for point in points}
        item_by_name = {item.canonical_name.casefold(): item for item in normalization.items}
        for point in points:
            item = item_by_name[point.name.casefold()]
            parent = point_by_name.get((item.parent_name or "").casefold())
            source_chunk_ids = [str(chunk_id) for chunk_id in item.source_chunk_ids]
            await self.knowledge.apply_normalization(
                point,
                chapter=item.chapter,
                parent_id=parent.id if parent else None,
                description=item.description,
                difficulty=item.difficulty,
                importance=item.importance,
                sort_order=item.sort_order,
                normalization_meta={
                    "aliases": item.aliases,
                    "confidence": item.confidence,
                    "decision_reason": item.decision_reason,
                    "source_chunk_ids": source_chunk_ids,
                    "source_material_ids": [str(material.id)],
                    "used_llm": normalization.used_llm,
                    "fallback_reason": normalization.fallback_reason,
                },
            )
            await self.chunks.bind_knowledge(
                chunk_ids=item.source_chunk_ids,
                knowledge_id=point.id,
            )

        relations_created = 0
        actor = current_user
        if actor is None:
            from sqlalchemy import select

            from app.models.user import User

            actor = (
                await self.db.execute(select(User).where(User.id == material.uploaded_by))
            ).scalar_one_or_none()
        if actor is not None and points:
            from app.services.knowledge_graph_service import KnowledgeGraphService

            relations_created = await KnowledgeGraphService(self.db).infer_relations_after_material_extract(
                current_user=actor,
                course_id=material.course_id,
                owner_id=material.uploaded_by,
                material_text=full_text,
                new_points=points,
            )

        await self.db.commit()
        for p in points:
            await self.db.refresh(p)
        return KnowledgeExtractionResult(
            points=points,
            relations_created=relations_created,
            normalization=normalization,
        )

    def _extract_candidates_from_chunks(self, chunks: list[object]) -> list[KnowledgeCandidate]:
        candidates: list[KnowledgeCandidate] = []
        for chunk_order, chunk in enumerate(chunks):
            items = self._extract_by_rules(str(getattr(chunk, "content", "")))
            chunk_id = getattr(chunk, "id")
            for local_order, item in enumerate(items):
                candidates.append(
                    KnowledgeCandidate(
                        raw_name=item["name"],
                        description=item.get("description") or "",
                        chapter=item.get("chapter"),
                        source_chunk_ids=[chunk_id],
                        source_order=chunk_order * 100 + local_order,
                    )
                )
                if len(candidates) >= 80:
                    return candidates
        return candidates

    def _extract_by_rules(self, text: str) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []
        seen_names: set[str] = set()

        chapter_pattern = re.compile(
            r"(?:^|\n)\s*(?:#{1,6}\s*|第[一二三四五六七八九十百千\d]+[章节篇]"
            r"|Chapter\s+\d+[:：]?\s*"
            r"|[一二三四五六七八九十]+[、.]\s*)"
            r"([^\n]+)",
            re.MULTILINE,
        )
        current_chapter = None
        for match in chapter_pattern.finditer(text):
            name = match.group(1).strip()
            name = re.sub(r"^[：:]\s*", "", name)
            name = re.sub(r"[（(].+?[）)]", "", name).strip()
            if name and name not in seen_names and len(name) <= 64:
                seen_names.add(name)
                current_chapter = name
                results.append(
                    {
                        "name": name,
                        "chapter": current_chapter,
                        "description": "",
                    }
                )

        def_pattern = re.compile(
            r"(?:^|[\n。])([^\n。]{2,20}?)(?:是|指|为|：)\s*([^\n。]{5,200})",
            re.MULTILINE,
        )
        for match in def_pattern.finditer(text):
            name = match.group(1).strip()
            desc = match.group(2).strip()
            if (
                name
                and name not in seen_names
                and len(name) >= 2
                and not re.match(r"^[\d\s]+$", name)
            ):
                seen_names.add(name)
                results.append(
                    {
                        "name": name,
                        "chapter": current_chapter,
                        "description": desc[:200],
                    }
                )

        item_pattern = re.compile(
            r"(?:^|\n)\s*(?:\d+[.、）)]\s*|[（(][一二三四五六七八九十\d]+[）)]\s*)([^\n]{2,64})",
            re.MULTILINE,
        )
        for match in item_pattern.finditer(text):
            name = match.group(1).strip()
            if name and name not in seen_names and len(name) >= 2:
                seen_names.add(name)
                results.append(
                    {
                        "name": name,
                        "chapter": current_chapter,
                        "description": "",
                    }
                )

        return results[:40]
