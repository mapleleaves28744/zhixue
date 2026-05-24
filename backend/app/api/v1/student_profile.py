from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.profile import ProfileUpdate
from app.services.profile_service import ProfileService

router = APIRouter()


@router.get("")
async def get_profile(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    profile = await ProfileService(db).get_profile(current_user.id)
    return success_response(profile.model_dump(mode="json"), request=request)


@router.put("")
async def update_profile(
    payload: ProfileUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    profile = await ProfileService(db).update_profile(current_user.id, payload)
    return success_response(profile.model_dump(mode="json"), request=request)


@router.get("/summary")
async def get_summary(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    summary = await ProfileService(db).get_summary(current_user.id)
    return success_response(summary.model_dump(mode="json"), request=request)


@router.post("/rebuild")
async def rebuild_profile(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    profile = await ProfileService(db).rebuild(current_user.id)
    return success_response(profile.model_dump(mode="json"), request=request)


@router.get("/preferences")
async def get_preferences(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    prefs = await ProfileService(db).get_preferences(current_user.id)
    return success_response(
        [p.model_dump(mode="json") for p in prefs], request=request
    )
