from __future__ import annotations

import asyncio
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
    data = await TutorService(db).chat(payload=body, current_user=current_user)
    if body.stream:
        return StreamingResponse(
            _stream_chat_response(data.model_dump(mode="json")),
            media_type="text/event-stream",
        )
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


async def _stream_chat_response(payload: dict[str, object]) -> AsyncIterator[str]:
    answer = str(payload.get("answer") or "")
    if not answer:
        yield "event: delta\ndata: {\"content\": \"\"}\n\n"
    for start in range(0, len(answer), 48):
        chunk = answer[start:start + 48]
        yield f"event: delta\ndata: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.02)
    done_payload = {
        "agent_run_id": payload.get("agent_run_id"),
        "message_id": payload.get("message_id"),
        "citations": payload.get("citations") or [],
        "related_knowledge_points": payload.get("related_knowledge_points") or [],
        "follow_up_questions": payload.get("follow_up_questions") or [],
        "review_result": payload.get("review_result") or {},
    }
    yield f"event: done\ndata: {json.dumps(done_payload, ensure_ascii=False)}\n\n"
