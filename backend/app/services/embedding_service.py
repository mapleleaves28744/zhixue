from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.llm.embedding import get_embedding_provider
from app.models.chunk import DocumentChunk
from app.models.material import CourseMaterial
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
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="资料尚未切片，无法执行向量化",
                status_code=400,
            )

        provider = get_embedding_provider()
        texts = [c.content for c in chunk_list]
        embedded_count = 0

        for start in range(0, len(texts), EMBED_BATCH_SIZE):
            batch_texts = texts[start : start + EMBED_BATCH_SIZE]
            batch_chunks = chunk_list[start : start + EMBED_BATCH_SIZE]
            try:
                vectors = await provider.embed_texts(batch_texts)
                if len(vectors) != len(batch_chunks):
                    raise ValueError(
                        f"Embedding count mismatch: expected {len(batch_chunks)}, got {len(vectors)}"
                    )
                for chunk, vec in zip(batch_chunks, vectors):
                    await self.chunks.update_embedding(chunk, vec)
                    embedded_count += 1
            except Exception as exc:
                logger.exception(
                    "Embedding batch failed for material %s (batch %d)",
                    material_id,
                    start // EMBED_BATCH_SIZE,
                )
                raise BusinessException(
                    code=ErrorCode.VECTOR_SEARCH_FAILED,
                    detail="资料向量化失败，请检查 Embedding Provider 配置或稍后重试",
                    status_code=500,
                ) from exc

        if chunk_list and embedded_count == 0:
            raise BusinessException(
                code=ErrorCode.VECTOR_SEARCH_FAILED,
                detail="资料向量化失败，未生成任何向量",
                status_code=500,
            )

        material = await self.db.get(CourseMaterial, material_id)
        if material is not None:
            material.extra_meta = {
                **(material.extra_meta or {}),
                "embedded_count": embedded_count,
            }
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
