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
@router.post("/generate")
async def analyze_diagnosis(
    request: Request,
    course_id: UUID,
    trigger_evolution: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = DiagnosisService(db)
    report = await svc.analyze(
        current_user=current_user,
        course_id=course_id,
        trigger_evolution=trigger_evolution,
    )
    return success_response(report, request=request)


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
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        request=request,
    )


@router.get("/reports/{report_id}")
async def get_report(
    report_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    report = await DiagnosisService(db).get_report(report_id, current_user.id)
    return success_response(report, request=request)


@router.get("/mastery")
async def get_mastery(
    request: Request,
    course_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    mastery = await DiagnosisService(db).get_mastery(
        user_id=current_user.id,
        course_id=course_id,
    )
    return success_response(mastery, request=request)
