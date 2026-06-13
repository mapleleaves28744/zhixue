from uuid import UUID
from typing import Literal

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.learning_analytics import SessionHeartbeatRequest
from app.services.learning_analytics_service import LearningAnalyticsService

router = APIRouter()


@router.post("/sessions/heartbeat")
async def heartbeat(payload: SessionHeartbeatRequest, request: Request, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    session = await LearningAnalyticsService(db).heartbeat(current_user.id, payload)
    return success_response({"session_id": str(session.id), "active_seconds": session.active_seconds}, request=request)


@router.post("/sessions/{session_id}/end")
async def end_session(session_id: UUID, request: Request, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    session = await LearningAnalyticsService(db).end(current_user.id, session_id)
    return success_response({"session_id": str(session.id), "active_seconds": session.active_seconds}, request=request)


@router.get("/summary")
async def summary(
    request: Request,
    course_id: UUID | None = None,
    period: Literal["week", "month"] = "week",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    data = await LearningAnalyticsService(db).summary(current_user.id, course_id, period)
    return success_response(data.model_dump(mode="json"), request=request)
