"""A/B 测试 API。"""
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_admin
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.services.ab_test_service import ABTestService

router = APIRouter()


class ABTestCreateRequest(BaseModel):
    course_id: UUID
    name: str = Field(min_length=1, max_length=255)
    test_type: str = "strategy"
    control_config: dict[str, Any] = Field(default_factory=dict)
    treatment_config: dict[str, Any] = Field(default_factory=dict)
    traffic_split: float = Field(default=0.5, ge=0.0, le=1.0)
    description: str = ""


class MetricRecordRequest(BaseModel):
    metric_value: float


@router.post("/")
async def create_test(
    payload: ABTestCreateRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = ABTestService(db)
    test = await svc.create_test(
        course_id=payload.course_id,
        name=payload.name,
        test_type=payload.test_type,
        control_config=payload.control_config,
        treatment_config=payload.treatment_config,
        traffic_split=payload.traffic_split,
        description=payload.description,
    )
    await db.commit()
    return success_response(_serialize_test(test), request=request)


@router.get("/")
async def list_tests(
    request: Request,
    course_id: UUID | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = ABTestService(db)
    items, total = await svc.list_tests(course_id=course_id, status=status, page=page, page_size=page_size)
    return success_response(
        {"items": [_serialize_test(t) for t in items], "total": total},
        request=request,
    )


@router.post("/{test_id}/start")
async def start_test(
    test_id: UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    test = await ABTestService(db).start_test(test_id)
    await db.commit()
    return success_response(_serialize_test(test), request=request)


@router.post("/{test_id}/pause")
async def pause_test(
    test_id: UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    test = await ABTestService(db).pause_test(test_id)
    await db.commit()
    return success_response(_serialize_test(test), request=request)


@router.post("/{test_id}/complete")
async def complete_test(
    test_id: UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    test = await ABTestService(db).complete_test(test_id)
    await db.commit()
    return success_response(_serialize_test(test), request=request)


@router.get("/{test_id}/stats")
async def get_test_stats(
    test_id: UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    stats = await ABTestService(db).get_test_stats(test_id)
    return success_response(stats, request=request)


@router.post("/{test_id}/metric")
async def record_metric(
    test_id: UUID,
    payload: MetricRecordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    await ABTestService(db).record_metric(test_id, current_user.id, payload.metric_value)
    await db.commit()
    return success_response({"recorded": True}, request=request)


def _serialize_test(test: Any) -> dict[str, Any]:
    return {
        "id": str(test.id),
        "course_id": str(test.course_id),
        "name": test.name,
        "description": test.description,
        "test_type": test.test_type,
        "control_config": test.control_config,
        "treatment_config": test.treatment_config,
        "traffic_split": test.traffic_split,
        "status": test.status,
        "winner": test.winner,
        "created_at": test.created_at.isoformat() if test.created_at else None,
    }
