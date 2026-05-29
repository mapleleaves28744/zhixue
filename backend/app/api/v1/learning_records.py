from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.services.learning_record_service import LearningRecordService

router = APIRouter()


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
