"""pgvector 扩展和索引管理。

确保 pgvector 扩展已安装，并创建 HNSW 索引以加速向量检索。
"""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSION = 1024


async def ensure_pgvector_extension(db: AsyncSession) -> bool:
    """确保 pgvector 扩展已安装。返回是否可用。"""
    try:
        await db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await db.commit()
        logger.info("pgvector extension ensured")
        return True
    except Exception as exc:
        logger.warning("pgvector extension not available: %s", exc)
        await db.rollback()
        return False


async def ensure_hnsw_index(db: AsyncSession) -> bool:
    """为 document_chunks.embedding 创建 HNSW 索引。

    HNSW 比 IVFFlat 更适合动态数据集，无需预训练。
    """
    try:
        # 检查索引是否已存在
        result = await db.execute(
            text(
                "SELECT 1 FROM pg_indexes "
                "WHERE tablename = 'document_chunks' AND indexname = 'idx_document_chunks_embedding_hnsw'"
            )
        )
        if result.scalar():
            logger.debug("HNSW index already exists")
            return True

        # 检查是否有足够的数据
        count_result = await db.execute(
            text("SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL")
        )
        count = count_result.scalar() or 0
        if count < 100:
            logger.info("Not enough embeddings (%d) to create HNSW index, skipping", count)
            return False

        # 创建 HNSW 索引（cosine 距离）
        logger.info("Creating HNSW index on document_chunks.embedding (%d rows)...", count)
        await db.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw "
                "ON document_chunks USING hnsw (embedding vector_cosine_ops) "
                "WITH (m = 16, ef_construction = 64)"
            )
        )
        await db.commit()
        logger.info("HNSW index created successfully")
        return True
    except Exception as exc:
        logger.warning("Failed to create HNSW index: %s", exc)
        await db.rollback()
        return False


async def setup_pgvector(db: AsyncSession) -> dict[str, bool]:
    """完整的 pgvector 设置流程。"""
    has_extension = await ensure_pgvector_extension(db)
    has_index = False
    if has_extension:
        has_index = await ensure_hnsw_index(db)
    return {
        "extension_available": has_extension,
        "hnsw_index_available": has_index,
    }
