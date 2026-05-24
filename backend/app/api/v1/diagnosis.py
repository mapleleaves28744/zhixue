from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.services.diagnosis_service import DiagnosisService

router = APIRouter()


@router.post("/analyze")
async def analyze_diagnosis(
    request: Request,
    course_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = DiagnosisService(db)
    report = await svc.analyze(
        user_id=current_user.id,
        course_id=course_id,
    )
    return success_response(report.model_dump(), request=request)


@router.get("/reports")
async def list_reports(
    request: Request,
    course_id: UUID | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = DiagnosisService(db)
    items, total = await svc.list_reports(
        user_id=current_user.id,
        course_id=course_id,
        page=page,
        page_size=page_size,
    )
    return success_response(
        {
            "items": [r.model_dump() for r in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        request=request,
    )
