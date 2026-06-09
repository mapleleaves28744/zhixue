from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.knowledge import (
    ExtractKnowledgeRequest,
    KnowledgeSearchRequest,
)
from app.services.course_service import CourseService
from app.services.knowledge_service import KnowledgeService
from app.services.knowledge_search_service import KnowledgeSearchService
from app.services.material_service import MaterialService
from app.services.seed_knowledge_service import load_seed_quality_report
from app.services.wiki_graph_service import WikiGraphService

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
    results = await KnowledgeSearchService(db).search(
        current_user=current_user,
        course_id=body.course_id,
        query=body.query,
        top_k=body.top_k,
        knowledge_id=body.knowledge_id,
    )
    return success_response(
        results,
        request=request,
    )


@router.get("/graph/subgraph")
async def get_knowledge_subgraph(
    request: Request,
    course_id: UUID = Query(...),
    center_id: UUID = Query(...),
    depth: int = Query(default=2, ge=1, le=4),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    data = await WikiGraphService(db).get_subgraph(
        current_user=current_user,
        course_id=course_id,
        center_id=center_id,
        depth=depth,
    )
    return success_response(data, request=request)


@router.post("/extract-from-material")
async def extract_knowledge(
    body: ExtractKnowledgeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    await MaterialService(db).get_writable_material(body.material_id, current_user)
    points, relations_created = await KnowledgeService(db).extract_from_material(
        body.material_id,
        current_user=current_user,
    )
    return success_response(
        {
            "extracted_count": len(points),
            "relations_created": relations_created,
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
