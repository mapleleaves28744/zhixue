from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_student
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.tutor import (
    TutorChatRequest,
    TutorFeedbackRequest,
    TutorSaveToWikiRequest,
)
from app.services.tutor_service import TutorService


router = APIRouter()


@router.get("/ping")
async def ping(request: Request) -> dict[str, object]:
    return success_response({"module": "tutor", "status": "ok"}, request=request)


@router.post("/chat", response_model=None)
async def chat_tutor(
    body: TutorChatRequest,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> Any:
    if body.stream:
        return StreamingResponse(
            _stream_tutor_chat(TutorService(db), body, current_user),
            media_type="text/event-stream",
        )
    data = await TutorService(db).chat(payload=body, current_user=current_user)
    return success_response(data.model_dump(mode="json"), request=request)


@router.post("/ask")
async def ask_tutor_compat(
    body: TutorChatRequest,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    data = await TutorService(db).chat(payload=body, current_user=current_user)
    return success_response(data.model_dump(mode="json"), request=request)


@router.post("/messages/{message_id}/save-to-wiki")
async def save_answer_to_wiki(
    message_id: UUID,
    body: TutorSaveToWikiRequest,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    data = await TutorService(db).save_answer_to_wiki(
        message_id=message_id,
        payload=body,
        current_user=current_user,
    )
    return success_response(data, request=request)


@router.post("/messages/{message_id}/feedback")
async def submit_feedback(
    message_id: UUID,
    body: TutorFeedbackRequest,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    data = await TutorService(db).submit_feedback(
        message_id=message_id,
        payload=body,
        current_user=current_user,
    )
    return success_response(data, request=request)


async def _stream_tutor_chat(
    service: TutorService,
    body: TutorChatRequest,
    current_user: User,
) -> AsyncIterator[str]:
    try:
        async for item in service.stream_chat(payload=body, current_user=current_user):
            event_name = str(item.get("event") or "message")
            data = item.get("data") or {}
            if event_name == "delta" and not data.get("content"):
                continue
            yield f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    except Exception as exc:
        error_payload = {"message": str(exc) or "AI Tutor 请求失败"}
        yield f"event: error\ndata: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
