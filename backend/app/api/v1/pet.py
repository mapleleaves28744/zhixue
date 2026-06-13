from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_student
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.pet import PetPreferenceUpdate
from app.services.pet_service import PetService

router = APIRouter()


@router.get("/feed")
async def get_feed(request: Request, current_user: User = Depends(require_student), db: AsyncSession = Depends(get_db)):
    return success_response(await PetService(db).feed(current_user), request=request)


@router.patch("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: UUID,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    result = await PetService(db).mark_read(notification_id, current_user)
    return success_response(result.model_dump(mode="json"), request=request)


@router.post("/notifications/read-all")
async def mark_all_read(request: Request, current_user: User = Depends(require_student), db: AsyncSession = Depends(get_db)):
    return success_response(await PetService(db).mark_all_read(current_user), request=request)


@router.get("/preferences")
async def get_preferences(request: Request, current_user: User = Depends(require_student), db: AsyncSession = Depends(get_db)):
    result = await PetService(db).get_preferences(current_user)
    return success_response(result.model_dump(mode="json"), request=request)


@router.put("/preferences")
async def update_preferences(
    payload: PetPreferenceUpdate,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    result = await PetService(db).update_preferences(payload, current_user)
    return success_response(result.model_dump(mode="json"), request=request)
