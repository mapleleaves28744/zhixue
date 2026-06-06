from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.rag.hybrid_retriever import HybridRetriever
from app.schemas.knowledge import (
    ExtractKnowledgeRequest,
    KnowledgeSearchRequest,
)
from app.services.course_service import CourseService
from app.services.knowledge_service import KnowledgeService
from app.services.material_service import MaterialService
from app.services.seed_knowledge_service import load_seed_quality_report

router = APIRouter()


@router.get("/seed-quality-report")
async def get_seed_quality_report(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    _ = current_user
    return success_response(load_seed_quality_report(), request=request)


@router.post("/search")
async def search_knowledge(
    body: KnowledgeSearchRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    await CourseService(db).get_course(body.course_id, current_user)
    results = await HybridRetriever(db).search(
        course_id=body.course_id,
        query=body.query,
        user_id=None if current_user.role == "admin" else current_user.id,
        top_k=body.top_k,
        knowledge_id=body.knowledge_id,
    )
    return success_response(
        [
            {
                "chunk_id": str(r.chunk_id),
                "content": r.content,
                "score": round(r.score, 4),
                "source_title": r.source_title,
                "page_no": r.page_no,
                "material_id": str(r.material_id),
                "retrieval_mode": r.retrieval_mode,
                "vector_score": round(r.vector_score, 4),
                "keyword_score": round(r.keyword_score, 4),
                "rerank_score": round(r.rerank_score, 4),
                "extra_meta": r.extra_meta,
            }
            for r in results
        ],
        request=request,
    )


@router.post("/extract-from-material")
async def extract_knowledge(
    body: ExtractKnowledgeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    await MaterialService(db).get_writable_material(body.material_id, current_user)
    points = await KnowledgeService(db).extract_from_material(body.material_id)
    return success_response(
        {
            "extracted_count": len(points),
            "points": [
                {
                    "id": str(p.id),
                    "owner_id": str(p.owner_id),
                    "scope": p.scope,
                    "name": p.name,
                    "chapter": p.chapter,
                    "description": p.description,
                }
                for p in points
            ],
        },
        request=request,
    )
