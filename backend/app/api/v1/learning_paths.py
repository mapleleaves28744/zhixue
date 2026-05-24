from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.learning_path import LearningPathGenerateRequest, LearningPathItemUpdate
from app.services.learning_path_service import LearningPathService

router = APIRouter()


@router.get("")
async def list_paths(
    request: Request,
    course_id: UUID | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    items, total = await LearningPathService(db).list_paths(
        current_user=current_user,
        course_id=course_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return success_response(
        {
            "items": [item.model_dump(mode="json") for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        request=request,
    )


@router.post("/generate")
async def generate_path(
    payload: LearningPathGenerateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    path = await LearningPathService(db).generate(payload=payload, current_user=current_user)
    return success_response(path.model_dump(mode="json"), request=request)


@router.get("/{path_id}")
async def get_path(
    path_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    path = await LearningPathService(db).get_path(path_id, current_user)
    return success_response(path.model_dump(mode="json"), request=request)


@router.patch("/items/{item_id}")
async def update_item(
    item_id: UUID,
    payload: LearningPathItemUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    item = await LearningPathService(db).update_item(
        item_id=item_id,
        payload=payload,
        current_user=current_user,
    )
    return success_response(item.model_dump(mode="json"), request=request)


@router.delete("/{path_id}")
async def archive_path(
    path_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    path = await LearningPathService(db).archive_path(path_id, current_user)
    return success_response(path.model_dump(mode="json"), request=request)
