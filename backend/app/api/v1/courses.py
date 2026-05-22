from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.core.response import page_response, success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.course import CourseCreate, CourseStatusFilter, CourseUpdate
from app.services.course_service import CourseService


router = APIRouter()


@router.get("/ping")
async def ping(request: Request) -> dict[str, object]:
    return success_response({"module": "courses", "status": "ok"}, request=request)


@router.post("")
async def create_course(
    payload: CourseCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    course = await CourseService(db).create_course(payload, current_user)
    return success_response(course.model_dump(mode="json"), request=request)


@router.get("")
async def list_courses(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: CourseStatusFilter = Query(default="active"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    courses, total = await CourseService(db).list_courses(
        current_user=current_user,
        page=page,
        page_size=page_size,
        status=status,
    )
    return page_response(
        items=[course.model_dump(mode="json") for course in courses],
        total=total,
        page=page,
        page_size=page_size,
        request=request,
    )


@router.get("/{course_id}")
async def get_course(
    course_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    course = await CourseService(db).get_course(course_id, current_user)
    return success_response(course.model_dump(mode="json"), request=request)


@router.put("/{course_id}")
async def update_course(
    course_id: UUID,
    payload: CourseUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        course = await CourseService(db).update_course(course_id, payload, current_user)
    except ValueError as exc:
        raise BusinessException(
            code=ErrorCode.PARAM_ERROR,
            detail=str(exc),
            status_code=400,
        ) from exc
    return success_response(course.model_dump(mode="json"), request=request)


@router.delete("/{course_id}")
async def archive_course(
    course_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    course = await CourseService(db).archive_course(course_id, current_user)
    return success_response(course.model_dump(mode="json"), request=request)
