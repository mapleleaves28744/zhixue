from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_student
from app.core.response import page_response, success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.resource import ResourceGenerateRequest, ResourceSaveToWikiRequest
from app.services.resource_service import ResourceService


router = APIRouter()


@router.get("/ping")
async def ping(request: Request) -> dict[str, object]:
    return success_response({"module": "resources", "status": "ok"}, request=request)


@router.post("/generate")
async def generate_resource(
    payload: ResourceGenerateRequest,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    data = await ResourceService(db).generate_resource(
        payload=payload,
        current_user=current_user,
    )
    return success_response(data.model_dump(mode="json"), request=request)


@router.get("")
async def list_resources(
    request: Request,
    course_id: UUID | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    status: str | None = Query(default="active"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    items, total = await ResourceService(db).list_resources(
        current_user=current_user,
        course_id=course_id,
        resource_type=resource_type,
        status=status,
        page=page,
        page_size=page_size,
    )
    return page_response(
        items=[item.model_dump(mode="json") for item in items],
        total=total,
        page=page,
        page_size=page_size,
        request=request,
    )


@router.get("/{resource_id}")
async def get_resource(
    resource_id: UUID,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    resource = await ResourceService(db).get_resource(
        resource_id=resource_id,
        current_user=current_user,
    )
    return success_response(resource.model_dump(mode="json"), request=request)


@router.post("/{resource_id}/save-to-wiki")
async def save_resource_to_wiki(
    resource_id: UUID,
    payload: ResourceSaveToWikiRequest,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    data = await ResourceService(db).save_to_wiki(
        resource_id=resource_id,
        current_user=current_user,
        payload=payload,
    )
    return success_response(data, request=request)


@router.delete("/{resource_id}")
async def archive_resource(
    resource_id: UUID,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    resource = await ResourceService(db).archive_resource(
        resource_id=resource_id,
        current_user=current_user,
    )
    return success_response(resource.model_dump(mode="json"), request=request)
