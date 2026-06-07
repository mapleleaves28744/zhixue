from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.learning_record import ALLOWED_LEARNING_EVENT_TYPES, LearningEventBatchRequest
from app.services.learning_record_service import LearningRecordService

router = APIRouter()


def ensure_learning_event_type(event_type: str) -> None:
    if event_type not in ALLOWED_LEARNING_EVENT_TYPES:
        raise BusinessException(
            code=ErrorCode.PARAM_ERROR,
            detail=f"不支持的学习行为类型: {event_type}",
            status_code=400,
        )


@router.get("")
async def list_learning_records(
    request: Request,
    course_id: UUID | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    records = await LearningRecordService(db).list_records(
        user_id=current_user.id,
        course_id=course_id,
        event_type=event_type,
        limit=limit,
    )
    return success_response(
        {
            "items": [
                {
                    "id": str(record.id),
                    "course_id": str(record.course_id) if record.course_id else None,
                    "knowledge_id": str(record.knowledge_id) if record.knowledge_id else None,
                    "event_type": record.event_type,
                    "event_source": record.event_source,
                    "event_payload": record.event_payload or {},
                    "created_at": record.created_at.isoformat() if record.created_at else None,
                }
                for record in records
            ],
            "total": len(records),
        },
        request=request,
    )


@router.post("/events/batch")
async def record_learning_events(
    request: Request,
    payload: LearningEventBatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    service = LearningRecordService(db)
    for event in payload.events:
        ensure_learning_event_type(event.event_type)
        await service.record_event(
            user_id=current_user.id,
            course_id=event.course_id,
            knowledge_id=event.knowledge_id,
            event_type=event.event_type,
            event_source=event.event_source,
            event_payload=event.event_payload,
            commit=False,
        )
    await db.commit()
    return success_response({"recorded": len(payload.events)}, request=request)
