from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import page_response, success_response
from app.db.session import get_db
from app.models.user import User
from app.services.recommendation_service import RecommendationService

router = APIRouter()


@router.get("")
async def list_recommendations(
    request: Request,
    course_id: UUID | None = Query(default=None),
    status: str | None = Query(default="pending"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    items, total = await RecommendationService(db).list_recommendations(
        current_user=current_user,
        course_id=course_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return page_response(items=items, total=total, page=page, page_size=page_size, request=request)


@router.post("/refresh")
async def refresh_recommendations(
    request: Request,
    course_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    result = await RecommendationService(db).refresh_recommendations(
        current_user=current_user,
        course_id=course_id,
    )
    return success_response(result, request=request)


@router.patch("/{item_id}")
async def update_recommendation_status(
    item_id: UUID,
    request: Request,
    status: str = Query(default="completed"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    result = await RecommendationService(db).update_status(
        item_id=item_id,
        current_user=current_user,
        status=status,
    )
    return success_response(result, request=request)


@router.post("/{item_id}/feedback")
async def submit_recommendation_feedback(
    item_id: UUID,
    request: Request,
    helpful: bool | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    result = await RecommendationService(db).submit_feedback(
        item_id=item_id,
        current_user=current_user,
        helpful=helpful,
    )
    return success_response(result, request=request)
