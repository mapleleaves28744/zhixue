from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.memory import MemoryUpdate
from app.services.memory_service import MemoryService

router = APIRouter()


@router.get("")
async def list_memories(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    memories = await MemoryService(db).list_memories(current_user.id)
    return success_response(
        [m.model_dump(mode="json") for m in memories], request=request
    )


@router.post("/reflect")
async def reflect(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    memories = await MemoryService(db).reflect(current_user.id)
    return success_response(
        [m.model_dump(mode="json") for m in memories], request=request
    )


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    await MemoryService(db).delete_memory(memory_id, current_user.id)
    return success_response(message="删除成功", request=request)


@router.patch("/{memory_id}")
async def update_memory(
    memory_id: UUID,
    payload: MemoryUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    memory = await MemoryService(db).update_memory(
        memory_id, current_user.id, payload
    )
    return success_response(memory.model_dump(mode="json"), request=request)
