from __future__ import annotations

import json
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_student
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.agent_conversation import (
    AgentConversationCreateRequest,
    AgentMessageCreateRequest,
    AgentTaskResumeRequest,
)
from app.services.agent_conversation_service import AgentConversationService
from app.services.agent_queue_service import AgentEventBroker


router = APIRouter()


@router.post("/conversations")
async def create_conversation(
    body: AgentConversationCreateRequest,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    result = await AgentConversationService(db).create_conversation(body, current_user)
    return success_response(result.model_dump(mode="json"), request=request)


@router.get("/conversations")
async def list_conversations(
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    items = await AgentConversationService(db).list_conversations(current_user)
    return success_response({"items": [item.model_dump(mode="json") for item in items]}, request=request)


@router.get("/conversations/{conversation_id}/messages")
async def list_messages(
    conversation_id: UUID,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    items = await AgentConversationService(db).list_messages(conversation_id, current_user)
    return success_response({"items": [item.model_dump(mode="json") for item in items]}, request=request)


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: UUID,
    body: AgentMessageCreateRequest,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    result = await AgentConversationService(db).send_message(conversation_id, body, current_user)
    return success_response(result.model_dump(mode="json"), request=request)


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: UUID,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    result = await AgentConversationService(db).get_task(task_id, current_user)
    return success_response(result.model_dump(mode="json"), request=request)


@router.get("/tasks/{task_id}/events/history")
async def list_task_events(
    task_id: UUID,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    items = await AgentConversationService(db).list_events(task_id, current_user)
    return success_response(
        {"items": [item.model_dump(mode="json") for item in items]},
        request=request,
    )


@router.get("/tasks/{task_id}/events", response_model=None)
async def stream_task_events(
    task_id: UUID,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    service = AgentConversationService(db)
    await service.get_task(task_id, current_user)
    return StreamingResponse(
        _event_stream(task_id, service, AgentEventBroker()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/tasks/{task_id}/resume")
async def resume_task(
    task_id: UUID,
    body: AgentTaskResumeRequest,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    result = await AgentConversationService(db).resume_task(
        task_id,
        current_user,
        approved=body.approved,
    )
    return success_response(result.model_dump(mode="json"), request=request)


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: UUID,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    result = await AgentConversationService(db).cancel_task(task_id, current_user)
    return success_response(result.model_dump(mode="json"), request=request)


@router.post("/tasks/{task_id}/requeue")
async def requeue_task(
    task_id: UUID,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    result = await AgentConversationService(db).requeue_task(task_id, current_user)
    return success_response(result.model_dump(mode="json"), request=request)


async def _event_stream(
    task_id: UUID,
    service: AgentConversationService,
    broker: AgentEventBroker,
) -> AsyncIterator[str]:
    for event in await service.conversations.list_events(task_id):
        payload = {"sequence_no": event.sequence_no, **event.payload}
        yield f"event: {event.event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        if event.event_type in {"completed", "failed", "cancelled"}:
            return
    async for event in broker.stream(task_id):
        event_type = event["event_type"]
        yield f"event: {event_type}\ndata: {json.dumps(event['payload'], ensure_ascii=False)}\n\n"
