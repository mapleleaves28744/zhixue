from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import page_response, success_response
from app.db.session import get_db
from app.models.user import User
from app.services.agent_log_service import AgentLogService
from app.services.agent_service import AgentService

router = APIRouter()


@router.get("/ping")
async def ping(request: Request) -> dict[str, object]:
    return success_response({"module": "agents", "status": "ok"}, request=request)


class AgentRunRequest(BaseModel):
    task_type: str = Field(min_length=1, max_length=64)
    course_id: UUID
    params: dict[str, object] = Field(default_factory=dict)


@router.post("/run")
async def run_agent(
    body: AgentRunRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    service = AgentService(db)
    result = await service.run_task(
        task_type=body.task_type,
        user_id=current_user.id,
        course_id=body.course_id,
        params=body.params,
    )
    await db.commit()
    return success_response(
        {
            "success": result.success,
            "data": result.data,
            "message": result.message,
            "evidence": result.evidence,
            "next_actions": result.next_actions,
        },
        request=request,
    )


@router.get("/runs")
async def list_runs(
    request: Request,
    task_type: str | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    log_service = AgentLogService(db)
    items, total = await log_service.list_runs(
        user_id=current_user.id,
        task_type=task_type,
        status=status,
        page=page,
        page_size=page_size,
    )
    return page_response(
        items=[
            {
                "id": str(run.id),
                "task_type": run.task_type,
                "agent_name": run.agent_name,
                "status": run.status,
                "duration_ms": run.duration_ms,
                "error_message": run.error_message,
                "created_at": run.created_at.isoformat() if run.created_at else None,
            }
            for run in items
        ],
        total=total,
        page=page,
        page_size=page_size,
        request=request,
    )


@router.get("/runs/{run_id}")
async def get_run(
    run_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    log_service = AgentLogService(db)
    run = await log_service.get_run(run_id)
    if run is None:
        from app.core.error_codes import ErrorCode
        from app.core.exceptions import BusinessException

        raise BusinessException(
            code=ErrorCode.NOT_FOUND,
            detail="运行记录不存在",
            status_code=404,
        )
    return success_response(
        {
            "id": str(run.id),
            "task_type": run.task_type,
            "agent_name": run.agent_name,
            "input_payload": run.input_payload,
            "output_payload": run.output_payload,
            "status": run.status,
            "duration_ms": run.duration_ms,
            "error_message": run.error_message,
            "created_at": run.created_at.isoformat() if run.created_at else None,
        },
        request=request,
    )
