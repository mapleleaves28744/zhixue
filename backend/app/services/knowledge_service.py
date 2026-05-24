from __future__ import annotations

import logging
import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.knowledge import KnowledgePoint
from app.models.material import CourseMaterial
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.material_repository import MaterialRepository

logger = logging.getLogger(__name__)


class KnowledgeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.materials = MaterialRepository(db)
        self.chunks = ChunkRepository(db)
        self.knowledge = KnowledgeRepository(db)

    async def extract_from_material(self, material_id: UUID) -> list[KnowledgePoint]:
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

        # Combine chunk texts for extraction
        full_text = "\n\n".join(c.content for c in chunks)

        # Rule-based extraction: split by chapter headings and key patterns
        extracted = self._extract_by_rules(full_text)

        if not extracted:
            # Fallback: treat each chunk as a potential knowledge point
            extracted = [
                {"name": f"知识点-{i + 1}", "description": c.content[:200]}
                for i, c in enumerate(chunks[:10])
            ]

        # Deduplicate and persist
        points, new_count = await self.knowledge.create_batch_if_not_exists(
            course_id=material.course_id,
            items=extracted,
        )
        await self.db.commit()
        for p in points:
            await self.db.refresh(p)
        return points

    def _extract_by_rules(self, text: str) -> list[dict]:
        """Rule-based knowledge point extraction from text."""
        results: list[dict] = []
        seen_names: set[str] = set()

        # Pattern 1: Chapter headings (第X章, 第X节, Chapter X, etc.)
        chapter_pattern = re.compile(
            r"(?:^|\n|(?<=\.))(?:第[一二三四五六七八九十百千\d]+[章节篇]"
            r"|Chapter\s+\d+[:：]?\s*"
            r"|[一二三四五六七八九十]+[、.]\s*)"
            r"(.+)",
            re.MULTILINE,
        )
        current_chapter = None
        for match in chapter_pattern.finditer(text):
            name = match.group(1).strip()
            # Clean up the name
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

        # Pattern 2: Definition-like sentences (XX是..., XX指..., XX：)
        def_pattern = re.compile(
            r"(?:^|[\n。])([^\n。]{2,20}?)(?:是|指|为|：)\s*([^\n。]{5,200})",
            re.MULTILINE,
        )
        for match in def_pattern.finditer(text):
            name = match.group(1).strip()
            desc = match.group(2).strip()
            # Filter out noise
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

        # Pattern 3: Bold / numbered items (1. XXX, （一）XXX)
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

        return results[:50]  # Cap at 50 knowledge points per material
