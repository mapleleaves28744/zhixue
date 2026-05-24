from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import DocumentChunk


class ChunkRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_batch(self, rows: list[dict]) -> list[DocumentChunk]:
        chunks = [DocumentChunk(**row) for row in rows]
        self.db.add_all(chunks)
        await self.db.flush()
        for chunk in chunks:
            await self.db.refresh(chunk)
        return chunks

    async def delete_by_material(self, material_id: UUID) -> int:
        result = await self.db.execute(
            delete(DocumentChunk).where(DocumentChunk.material_id == material_id)
        )
        return result.rowcount  # type: ignore[return-value]

    async def list_by_material(self, material_id: UUID) -> list[DocumentChunk]:
        result = await self.db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.material_id == material_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return list(result.scalars().all())

    async def list_by_course(self, course_id: UUID) -> list[DocumentChunk]:
        result = await self.db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.course_id == course_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return list(result.scalars().all())

    async def get_by_id(self, chunk_id: UUID) -> DocumentChunk | None:
        result = await self.db.execute(
            select(DocumentChunk).where(DocumentChunk.id == chunk_id)
        )
        return result.scalar_one_or_none()

    async def update_embedding(self, chunk: DocumentChunk, embedding: list[float]) -> None:
        chunk.embedding = embedding  # type: ignore[assignment]
        await self.db.flush()
