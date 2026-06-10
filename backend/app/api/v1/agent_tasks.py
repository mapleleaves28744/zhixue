from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.agent_task import AgentTaskCreateRequest
from app.services.agent_task_service import AgentTaskService

router = APIRouter()


@router.post("/create")
async def create_agent_task(
    payload: AgentTaskCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    task = await AgentTaskService(db).create_task(payload=payload, current_user=current_user)
    return success_response(task.model_dump(mode="json"), request=request)


@router.get("/{task_id}")
async def get_agent_task(
    task_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    task = await AgentTaskService(db).get_task(task_id, current_user)
    return success_response(task.model_dump(mode="json"), request=request)


@router.get("/{task_id}/steps")
async def get_agent_task_steps(
    task_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    items = await AgentTaskService(db).get_steps(task_id, current_user)
    return success_response(
        {"items": [item.model_dump(mode="json") for item in items]},
        request=request,
    )


@router.post("/{task_id}/confirm")
async def confirm_agent_task(
    task_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    task = await AgentTaskService(db).confirm_task(task_id, current_user)
    return success_response(task.model_dump(mode="json"), request=request)


@router.post("/{task_id}/run")
async def run_agent_task(
    task_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    task = await AgentTaskService(db).run_task(task_id, current_user)
    return success_response(task.model_dump(mode="json"), request=request)


@router.post("/{task_id}/cancel")
async def cancel_agent_task(
    task_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    task = await AgentTaskService(db).cancel_task(task_id, current_user)
    return success_response(task.model_dump(mode="json"), request=request)

