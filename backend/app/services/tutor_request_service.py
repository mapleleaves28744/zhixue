from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.agent_conversation import AgentConversation
from app.models.tutor_request import TutorRequest
from app.repositories.agent_conversation_repository import AgentConversationRepository
from app.schemas.tutor import TutorChatRequest, TutorChatResponse


@dataclass(frozen=True)
class TutorClaim:
    request_id: UUID
    owner: str | None = None
    version: int = 0
    completed: TutorChatResponse | None = None


class TutorRequestService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def claim(self, payload: TutorChatRequest, user_id: UUID) -> TutorClaim | None:
        if payload.conversation_id is None or payload.client_request_id is None:
            return None
        conversation = (await self.db.execute(select(AgentConversation).where(
            AgentConversation.id == payload.conversation_id,
            AgentConversation.user_id == user_id,
            AgentConversation.course_id == payload.course_id,
        ).with_for_update())).scalar_one_or_none()
        if conversation is None:
            raise BusinessException(code=ErrorCode.NOT_FOUND, detail="当前课程的会话不存在", status_code=404)
        existing = (await self.db.execute(select(TutorRequest).where(
            TutorRequest.conversation_id == conversation.id,
            TutorRequest.client_request_id == payload.client_request_id,
        ).execution_options(populate_existing=True))).scalar_one_or_none()
        request_data = payload.model_dump(mode="json", exclude={"stream", "client_request_id"})
        now = datetime.now(UTC)
        if existing is not None:
            if existing.request_payload != request_data:
                raise BusinessException(code=ErrorCode.CONFLICT, detail="同一请求 ID 的内容不一致", status_code=409)
            if existing.status == "succeeded" and existing.response_payload:
                return TutorClaim(existing.id, completed=TutorChatResponse.model_validate(existing.response_payload))
            committed_message = await AgentConversationRepository(self.db).get_request_message(
                conversation.id, payload.client_request_id,
            )
            if committed_message is not None and committed_message.role == "assistant":
                completed = TutorChatResponse.model_validate(committed_message.payload)
                existing.status = "succeeded"
                existing.response_payload = completed.model_dump(mode="json")
                existing.lease_owner = None
                existing.lease_until = None
                await self.db.commit()
                return TutorClaim(existing.id, completed=completed)
            if existing.status == "running" and existing.lease_until and existing.lease_until > now:
                raise BusinessException(code=ErrorCode.CONFLICT, detail="该请求仍在处理中，请稍后查询结果", status_code=409)
            existing.lease_version += 1
            existing.status = "running"
            existing.error_message = None
            request = existing
        else:
            request = TutorRequest(
                conversation_id=conversation.id, user_id=user_id,
                client_request_id=payload.client_request_id, request_payload=request_data,
            )
            self.db.add(request)
        owner = uuid4().hex
        request.lease_owner = owner
        request.lease_until = now + timedelta(minutes=5)
        request.updated_at = now
        await self.db.commit()
        return TutorClaim(request.id, owner=owner, version=request.lease_version)

    async def complete(self, claim: TutorClaim | None, response: TutorChatResponse) -> None:
        if claim is None:
            return
        request = (await self.db.execute(select(TutorRequest).where(TutorRequest.id == claim.request_id).with_for_update().execution_options(populate_existing=True))).scalar_one()
        if request.status == "succeeded" and request.response_payload:
            if request.lease_version != claim.version:
                raise BusinessException(code=ErrorCode.CONFLICT, detail="旧请求已失去提交资格", status_code=409)
            if request.response_payload.get("answer") != response.answer:
                raise BusinessException(code=ErrorCode.CONFLICT, detail="已完成请求的回答不一致", status_code=409)
            request.response_payload = response.model_dump(mode="json")
            await self.db.commit()
            return
        if request.status != "running" or request.lease_owner != claim.owner or request.lease_version != claim.version:
            raise BusinessException(code=ErrorCode.CONFLICT, detail="旧请求已失去提交资格", status_code=409)
        request.status = "succeeded"
        request.response_payload = response.model_dump(mode="json")
        request.lease_owner = None
        request.lease_until = None
        request.updated_at = datetime.now(UTC)
        await self.db.commit()

    async def assert_owner(self, claim: TutorClaim | None) -> None:
        if claim is None:
            return
        request = (await self.db.execute(select(TutorRequest).where(TutorRequest.id == claim.request_id).with_for_update().execution_options(populate_existing=True))).scalar_one()
        if request.status != "running" or request.lease_owner != claim.owner or request.lease_version != claim.version:
            raise BusinessException(code=ErrorCode.CONFLICT, detail="旧请求已失去提交资格", status_code=409)

    async def fail(self, claim: TutorClaim | None, error: Exception) -> None:
        if claim is None:
            return
        await self.db.rollback()
        request = (await self.db.execute(select(TutorRequest).where(TutorRequest.id == claim.request_id).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
        if request is None or request.lease_owner != claim.owner or request.lease_version != claim.version:
            await self.db.rollback()
            return
        request.status = "failed"
        request.error_message = str(error)[:1000]
        request.lease_owner = None
        request.lease_until = None
        request.updated_at = datetime.now(UTC)
        await self.db.commit()

    async def status(self, *, conversation_id: UUID, client_request_id: UUID, user_id: UUID) -> dict[str, object]:
        request = (await self.db.execute(select(TutorRequest).where(
            TutorRequest.conversation_id == conversation_id,
            TutorRequest.client_request_id == client_request_id,
            TutorRequest.user_id == user_id,
        ).execution_options(populate_existing=True))).scalar_one_or_none()
        if request is None:
            raise BusinessException(code=ErrorCode.NOT_FOUND, detail="请求不存在", status_code=404)
        if request.status != "succeeded":
            committed_message = await AgentConversationRepository(self.db).get_request_message(
                conversation_id, client_request_id,
            )
            if committed_message is not None and committed_message.role == "assistant":
                completed = TutorChatResponse.model_validate(committed_message.payload)
                request.status = "succeeded"
                request.response_payload = completed.model_dump(mode="json")
                request.lease_owner = None
                request.lease_until = None
                await self.db.commit()
        return {"status": request.status, "response": request.response_payload, "error_message": request.error_message}
