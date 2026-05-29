from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import page_response, success_response
from app.db.session import get_db
from app.models.user import User
from app.services.chunk_service import ChunkService
from app.services.embedding_service import EmbeddingService
from app.services.material_service import MaterialService


router = APIRouter()


@router.get("/ping")
async def ping(request: Request) -> dict[str, object]:
    return success_response({"module": "materials", "status": "ok"}, request=request)


@router.post("/upload")
async def upload_material(
    request: Request,
    course_id: UUID = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    material = await MaterialService(db).upload_material(
        course_id=course_id,
        upload=file,
        current_user=current_user,
    )
    return success_response(material.model_dump(mode="json"), request=request)


@router.get("")
async def list_materials(
    request: Request,
    course_id: UUID = Query(...),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    materials, total = await MaterialService(db).list_materials(
        course_id=course_id,
        current_user=current_user,
        page=page,
        page_size=page_size,
    )
    return page_response(
        items=[material.model_dump(mode="json") for material in materials],
        total=total,
        page=page,
        page_size=page_size,
        request=request,
    )


@router.get("/{material_id}")
async def get_material(
    material_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    material = await MaterialService(db).get_material(material_id, current_user)
    return success_response(material.model_dump(mode="json"), request=request)


@router.get("/{material_id}/parse-status")
async def get_parse_status(
    material_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    status = await MaterialService(db).get_parse_status(material_id, current_user)
    return success_response(status.model_dump(mode="json"), request=request)


@router.post("/{material_id}/parse")
async def parse_material(
    material_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    result = await MaterialService(db).parse_material(material_id, current_user)
    return success_response(result.model_dump(mode="json"), request=request)


@router.post("/{material_id}/chunk")
async def chunk_material(
    material_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    material = await MaterialService(db).get_writable_material(material_id, current_user)
    chunks = await ChunkService(db).chunk_material(material)
    return success_response(
        {
            "material_id": str(material_id),
            "chunk_count": len(chunks),
        },
        request=request,
    )


@router.post("/{material_id}/embed")
async def embed_material(
    material_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    await MaterialService(db).get_writable_material(material_id, current_user)
    count = await EmbeddingService(db).generate_embeddings(material_id)
    return success_response(
        {
            "material_id": str(material_id),
            "embedded_count": count,
        },
        request=request,
    )
