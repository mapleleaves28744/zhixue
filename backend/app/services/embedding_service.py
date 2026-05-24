from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.embedding import get_embedding_provider
from app.models.chunk import DocumentChunk
from app.repositories.chunk_repository import ChunkRepository

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 16


class EmbeddingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.chunks = ChunkRepository(db)

    async def generate_embeddings(self, material_id: UUID) -> int:
        chunk_list = await self.chunks.list_by_material(material_id)
        if not chunk_list:
            return 0

        provider = get_embedding_provider()
        texts = [c.content for c in chunk_list]
        embedded_count = 0

        for start in range(0, len(texts), EMBED_BATCH_SIZE):
            batch_texts = texts[start : start + EMBED_BATCH_SIZE]
            batch_chunks = chunk_list[start : start + EMBED_BATCH_SIZE]
            try:
                vectors = await provider.embed_texts(batch_texts)
                for chunk, vec in zip(batch_chunks, vectors):
                    await self.chunks.update_embedding(chunk, vec)
                    embedded_count += 1
            except Exception:
                logger.exception(
                    "Embedding batch failed for material %s (batch %d)",
                    material_id,
                    start // EMBED_BATCH_SIZE,
                )

        await self.db.commit()
        return embedded_count

    async def generate_for_chunk(self, chunk_id: UUID) -> DocumentChunk:
        chunk = await self.chunks.get_by_id(chunk_id)
        if chunk is None:
            from app.core.error_codes import ErrorCode
            from app.core.exceptions import BusinessException

            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="文档切片不存在",
                status_code=404,
            )

        provider = get_embedding_provider()
        vectors = await provider.embed_texts([chunk.content])
        await self.chunks.update_embedding(chunk, vectors[0])
        await self.db.commit()
        await self.db.refresh(chunk)
        return chunk
