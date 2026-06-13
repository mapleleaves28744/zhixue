from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_student
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.multimodal import (
    EducationalImageGenerateRequest,
    ImmersiveClassroomGenerateRequest,
    InteractiveCoursewareGenerateRequest,
    LessonVideoGenerateRequest,
    StoryboardHtmlGenerateRequest,
)
from app.services.multimodal_resource_service import MultimodalResourceService
from app.services.immersive_classroom_service import ImmersiveClassroomService

router = APIRouter()


@router.post("/classrooms/generate")
async def generate_immersive_classroom(
    payload: ImmersiveClassroomGenerateRequest,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    data = await ImmersiveClassroomService(db).create_job(
        current_user=current_user,
        course_id=payload.course_id,
        topic=payload.topic,
        learning_goal=payload.learning_goal,
        generate_video_export=payload.generate_video_export,
        enable_images=payload.enable_images,
        enable_video_clips=payload.enable_video_clips,
        enable_tts=payload.enable_tts,
    )
    return success_response(data, request=request)


@router.post("/images/generate")
async def generate_image(
    payload: EducationalImageGenerateRequest,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    data = await MultimodalResourceService(db).generate_image(
        current_user=current_user,
        course_id=payload.course_id,
        topic=payload.topic,
        image_type=payload.image_type,
        style=payload.style,
        size=payload.size,
        requirement=payload.requirement,
    )
    return success_response(data, request=request)


@router.post("/videos/generate")
async def generate_video(
    payload: LessonVideoGenerateRequest,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    data = await MultimodalResourceService(db).create_video_job(
        current_user=current_user,
        course_id=payload.course_id,
        topic=payload.topic,
        duration_seconds=payload.duration_seconds,
        visual_mode=payload.visual_mode,
        voice=payload.voice,
        target_level=payload.target_level,
    )
    return success_response(data, request=request)


@router.post("/storyboard/generate")
async def generate_storyboard(
    payload: StoryboardHtmlGenerateRequest,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    data = await MultimodalResourceService(db).generate_storyboard_html(
        current_user=current_user,
        course_id=payload.course_id,
        topic=payload.topic,
        duration_seconds=payload.duration_seconds,
        requirement=payload.requirement,
    )
    return success_response(data, request=request)


@router.post("/courseware/generate")
async def generate_courseware(
    payload: InteractiveCoursewareGenerateRequest,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    data = await MultimodalResourceService(db).generate_courseware(
        current_user=current_user,
        course_id=payload.course_id,
        topic=payload.topic,
        interaction_type=payload.interaction_type,
        target_level=payload.target_level,
        requirement=payload.requirement,
    )
    return success_response(data, request=request)


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: UUID,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    from app.repositories.media_repository import MediaRepository
    from app.schemas.multimodal import MediaJobRead

    job = await MediaRepository(db).get_job_for_user(job_id, current_user.id)
    if job is None:
        from app.core.error_codes import ErrorCode
        from app.core.exceptions import BusinessException

        raise BusinessException(code=ErrorCode.NOT_FOUND, detail="媒体任务不存在", status_code=404)
    return success_response(MediaJobRead.model_validate(job).model_dump(mode="json"), request=request)
