from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.chunk import DocumentChunk
from app.models.material import CourseMaterial
from app.rag.chunking import chunk_text
from app.repositories.chunk_repository import ChunkRepository


class ChunkService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.chunks = ChunkRepository(db)

    async def chunk_material(self, material: CourseMaterial) -> list[DocumentChunk]:
        extra_meta = material.extra_meta or {}
        parsed_text_path = extra_meta.get("parsed_text_path")
        if not parsed_text_path:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="资料尚未解析，请先调用解析接口",
                status_code=400,
            )

        text = Path(parsed_text_path).read_text(encoding="utf-8").strip()
        if not text:
            raise BusinessException(
                code=ErrorCode.FILE_PARSE_FAILED,
                detail="解析文本为空，无法切片",
                status_code=400,
            )

        chunk_data_list = chunk_text(text)
        if not chunk_data_list:
            raise BusinessException(
                code=ErrorCode.FILE_PARSE_FAILED,
                detail="切片结果为空",
                status_code=400,
            )

        # Idempotent: delete existing chunks for this material first
        await self.chunks.delete_by_material(material.id)
        await self.db.flush()

        rows = [
            {
                "material_id": material.id,
                "course_id": material.course_id,
                "chunk_index": cd.index,
                "content": cd.content,
                "token_count": cd.token_count,
                "source_title": material.file_name,
            }
            for cd in chunk_data_list
        ]
        created = await self.chunks.create_batch(rows)
        material.extra_meta = {
            **(material.extra_meta or {}),
            "chunk_count": len(created),
        }
        await self.db.commit()
        for chunk in created:
            await self.db.refresh(chunk)
        return created

    async def get_chunks_by_material(self, material_id: UUID) -> list[DocumentChunk]:
        return await self.chunks.list_by_material(material_id)
