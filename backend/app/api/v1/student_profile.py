from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.profile import ProfileDialogueIngestRequest, ProfileUpdate
from app.services.course_service import CourseService
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
    course_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    if course_id is not None:
        await CourseService(db).get_readable_course(course_id, current_user)
        profile = await ProfileService(db).rebuild_course(current_user.id, course_id)
    else:
        profile = await ProfileService(db).rebuild(current_user.id)
    return success_response(profile.model_dump(mode="json"), request=request)


@router.get("/course/{course_id}")
async def get_course_profile(
    course_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    await CourseService(db).get_readable_course(course_id, current_user)
    profile = await ProfileService(db).get_course_profile(current_user.id, course_id)
    return success_response(profile.model_dump(mode="json"), request=request)


@router.post("/dialogue-ingest")
async def ingest_dialogue_profile(
    payload: ProfileDialogueIngestRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    if payload.course_id is not None:
        await CourseService(db).get_readable_course(payload.course_id, current_user)
    result = await ProfileService(db).ingest_dialogue_profile(
        user_id=current_user.id,
        course_id=payload.course_id,
        dialogue_text=payload.dialogue_text,
        source_message_id=payload.source_message_id,
    )
    return success_response(result.model_dump(mode="json"), request=request)


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
