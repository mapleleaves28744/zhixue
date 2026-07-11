from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.course import Course
from app.models.learning_record import LearningRecord
from app.models.user import User
from app.models.wiki import WikiPage
from app.repositories.course_repository import CourseRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.wiki_repository import WikiRepository
from app.schemas.tutor import (
    TutorChatRequest,
    TutorChatResponse,
    TutorFeedbackRequest,
    TutorSaveToWikiRequest,
)
from app.services.course_service import CourseService
from app.services.conversation_intent import is_simple_greeting
from app.services.grounded_qa_pipeline import GroundedQaPipeline
from app.services.learning_record_service import LearningRecordService


logger = logging.getLogger(__name__)


VALID_FEEDBACK_TYPES = {"like", "dislike", "useful", "useless", "report_error"}


class TutorService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.courses = CourseRepository(db)
        self.wiki = WikiRepository(db)
        self.feedback = FeedbackRepository(db)
        self.records = LearningRecordService(db)

    async def chat(
        self,
        *,
        payload: TutorChatRequest,
        current_user: User,
    ) -> TutorChatResponse:
        from app.agent_runtime import supervisor_intents

        if supervisor_intents.web_search_intent(payload.question):
            course = await self._get_accessible_course(payload.course_id, current_user)
            if payload.wiki_page_id is not None:
                await self._get_readable_wiki_page(payload.wiki_page_id, course, current_user)
            async for event in self._stream_web_search_answer(
                payload=payload,
                current_user=current_user,
                course=course,
            ):
                if event.get("event") == "done":
                    return TutorChatResponse.model_validate(event.get("data") or {})
            raise BusinessException(
                code=ErrorCode.LLM_CALL_FAILED,
                detail="联网问答未返回结果",
                status_code=500,
            )
        return await GroundedQaPipeline(self.db).answer(payload, current_user)

    async def stream_chat(
        self,
        *,
        payload: TutorChatRequest,
        current_user: User,
    ) -> AsyncIterator[dict[str, Any]]:
        from app.agent_runtime import supervisor_intents

        if supervisor_intents.web_search_intent(payload.question):
            course = await self._get_accessible_course(payload.course_id, current_user)
            if payload.wiki_page_id is not None:
                await self._get_readable_wiki_page(payload.wiki_page_id, course, current_user)
            async for item in self._stream_web_search_answer(
                payload=payload,
                current_user=current_user,
                course=course,
            ):
                yield item
            return
        async for event in GroundedQaPipeline(self.db).stream(payload, current_user):
            yield event

    async def _stream_web_search_answer(
        self,
        *,
        payload: TutorChatRequest,
        current_user: User,
        course: Course,
    ) -> AsyncIterator[dict[str, Any]]:
        from app.agent_runtime.supervisor import MiMoSupervisor
        from app.services.web_search_service import WebSearchService

        yield {"event": "progress", "data": {"stage": "web_search", "message": "联网搜索中…"}}
        result = await WebSearchService().search(query=payload.question, max_results=5)
        answer = MiMoSupervisor(provider=object())._format_search_output_answer(  # type: ignore[arg-type]
            "search_web",
            result,
            payload.question,
        )
        citations = list(result.get("citations") or [])
        chunk_size = 120
        for index in range(0, len(answer), chunk_size):
            yield {"event": "delta", "data": {"content": answer[index : index + chunk_size]}}

        review_result = self._rule_review_answer(answer=answer, citations=citations)
        record = await self.records.record_event(
            user_id=current_user.id,
            course_id=course.id,
            knowledge_id=payload.knowledge_id,
            event_type="chat",
            event_source="tutor",
            event_payload={
                "question": payload.question,
                "answer": answer,
                "citations": citations,
                "related_knowledge_points": [],
                "follow_up_questions": [],
                "review_result": review_result,
                "provider": result.get("provider") or "anysearch",
                "fallback_used": result.get("provider") == "mock",
            },
        )
        response_payload = {
            "answer": answer,
            "citations": citations,
            "related_knowledge_points": [],
            "follow_up_questions": [],
            "review_result": review_result,
            "memory_update_suggestion": {"should_reflect": False, "reason": "联网搜索问答不写入长期记忆。"},
            "message_id": record.id,
            "provider": result.get("provider") or "anysearch",
            "fallback_used": result.get("provider") == "mock",
        }
        await self._maybe_schedule_practice_prepush(
            user_id=current_user.id,
            course_id=course.id,
        )
        await self._maybe_schedule_external_resource_prepush(
            user_id=current_user.id,
            course_id=course.id,
        )
        yield {
            "event": "done",
            "data": TutorChatResponse.model_validate(response_payload).model_dump(mode="json"),
        }

    async def save_answer_to_wiki(
        self,
        *,
        message_id: UUID,
        payload: TutorSaveToWikiRequest,
        current_user: User,
    ) -> dict[str, Any]:
        record = await self._get_chat_record(message_id, current_user.id)
        course_id = record.course_id
        if course_id is None:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="问答记录缺少课程 ID",
                status_code=400,
            )
        course = await self._get_accessible_course(course_id, current_user)
        page = await self._get_writable_or_personal_copy(payload.wiki_page_id, course, current_user)
        event = record.event_payload or {}
        question = str(event.get("question") or "未记录问题")
        answer = str(event.get("answer") or "")
        citations = event.get("citations") or []
        section_title = payload.section_title or "AI Tutor 问答沉淀"
        new_content = (
            f"{page.content.rstrip()}\n\n---\n\n"
            f"## {section_title}\n\n"
            f"### 问题\n{question}\n\n"
            f"### 回答\n{answer}\n\n"
            "### 引用来源\n"
            f"{self._format_citations(citations)}"
        )
        new_version = page.current_version + 1

        await self.wiki.update_page(
            page,
            content=new_content,
            current_version=new_version,
        )
        await self.wiki.create_version(
            page_id=page.id,
            version_number=new_version,
            title=page.title,
            content=new_content,
            summary=page.summary,
            change_message="保存 AI Tutor 问答",
            created_by=current_user.id,
        )
        await self.wiki.create_source(
            page_id=page.id,
            source_type="chat",
            source_id=record.id,
            source_title="AI Tutor 问答",
            quote_text=answer[:200],
        )
        await self.db.commit()
        await self.db.refresh(page)

        await self.records.record_event(
            user_id=current_user.id,
            course_id=course_id,
            event_type="save_tutor_answer",
            event_source="tutor",
            event_payload={
                "message_id": str(message_id),
                "wiki_page_id": str(page.id),
                "wiki_page_title": page.title,
                "version_no": page.current_version,
            },
        )
        return {
            "message_id": str(message_id),
            "wiki_page": {
                "id": str(page.id),
                "title": page.title,
                "current_version": page.current_version,
            },
        }

    async def submit_feedback(
        self,
        *,
        message_id: UUID,
        payload: TutorFeedbackRequest,
        current_user: User,
    ) -> dict[str, Any]:
        record = await self._get_chat_record(message_id, current_user.id)
        feedback_type = payload.feedback_type.strip().lower()
        if feedback_type not in VALID_FEEDBACK_TYPES:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="feedback_type 只能是 like / dislike / useful / useless / report_error",
                status_code=400,
            )
        feedback = await self.feedback.create(
            user_id=current_user.id,
            course_id=record.course_id,
            target_type="chat",
            target_id=message_id,
            feedback_type=feedback_type,
            rating=payload.rating,
            comment=payload.comment,
        )
        await self.records.record_event(
            user_id=current_user.id,
            course_id=record.course_id,
            event_type="feedback",
            event_source="tutor",
            event_payload={
                "target_type": "chat",
                "target_id": str(message_id),
                "feedback_id": str(feedback.id),
                "feedback_type": feedback_type,
                "rating": payload.rating,
                "comment": payload.comment,
            },
        )
        await self.db.commit()
        return {
            "feedback_id": str(feedback.id),
            "message_id": str(message_id),
            "feedback_type": feedback_type,
        }

    def _rule_review_answer(
        self,
        *,
        answer: str,
        citations: list[Any],
    ) -> dict[str, Any]:
        has_sources = any(
            isinstance(item, dict) and item.get("source_type") not in {None, "inference"}
            for item in citations
        )
        return {
            "pass": bool(answer.strip()),
            "risk_level": "low" if has_sources or is_simple_greeting(answer) else "medium",
            "issues": [] if has_sources or is_simple_greeting(answer) else ["回答缺少明确课程来源，已标记为 AI 推断内容。"],
            "revision_suggestions": "",
            "reviewer": "fast_stream_rule",
        }

    async def _get_accessible_course(self, course_id: UUID, current_user: User) -> Course:
        return await CourseService(self.db).get_readable_course(course_id, current_user)

    async def _get_readable_wiki_page(
        self,
        page_id: UUID,
        course: Course,
        current_user: User,
    ) -> WikiPage:
        page = await self.wiki.get_by_id_simple(page_id)
        if page is None or page.course_id != course.id:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="Wiki 页面不存在",
                status_code=404,
            )
        if page.status == "archived":
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="已归档的 Wiki 页面不可更新",
                status_code=400,
            )
        if current_user.role == "admin" or page.owner_id == current_user.id:
            return page
        is_public_page = (
            course.visibility == "public_template"
            and page.owner_id == course.owner_id
        )
        if is_public_page:
            return page
        raise BusinessException(
            code=ErrorCode.NOT_FOUND,
            detail="Wiki 页面不存在",
            status_code=404,
        )

    async def _get_writable_or_personal_copy(
        self,
        page_id: UUID,
        course: Course,
        current_user: User,
    ) -> WikiPage:
        page = await self._get_readable_wiki_page(page_id, course, current_user)
        if current_user.role == "admin" or page.owner_id == current_user.id:
            return page
        is_public_page = (
            course.visibility == "public_template"
            and page.owner_id == course.owner_id
        )
        if not is_public_page:
            raise BusinessException(
                code=ErrorCode.FORBIDDEN,
                detail="无权编辑此 Wiki 页面",
                status_code=403,
            )
        copied = await self.wiki.create_page(
            course_id=course.id,
            owner_id=current_user.id,
            title=page.title,
            content=page.content,
            summary=page.summary,
        )
        await self.wiki.create_source(
            page_id=copied.id,
            source_type="manual",
            source_id=page.id,
            source_title=f"个人副本来源：{page.title}",
            quote_text=(page.summary or page.content[:200]),
        )
        return copied

    async def _get_chat_record(self, message_id: UUID, user_id: UUID) -> LearningRecord:
        record = await self.records.get_user_record(record_id=message_id, user_id=user_id)
        if record is None or record.event_type != "chat":
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="问答消息不存在",
                status_code=404,
            )
        return record

    async def _maybe_schedule_practice_prepush(self, *, user_id: UUID, course_id: UUID) -> None:
        try:
            from app.services.practice_prepush_service import PracticePrepushService

            await PracticePrepushService(self.db).schedule_from_recent_chat(
                user_id=user_id,
                course_id=course_id,
            )
        except Exception:
            logger.exception("schedule practice prepush failed")

    async def _maybe_schedule_external_resource_prepush(self, *, user_id: UUID, course_id: UUID) -> None:
        try:
            from app.services.external_resource_prepush_service import ExternalResourcePrepushService

            await ExternalResourcePrepushService(self.db).schedule_from_recent_chat(
                user_id=user_id,
                course_id=course_id,
            )
        except Exception:
            logger.exception("schedule external resource prepush failed")

    def _format_citations(self, citations: list[Any]) -> str:
        lines = []
        for citation in citations[:8]:
            if isinstance(citation, dict):
                title = citation.get("title") or citation.get("source_title") or "来源"
                source_type = citation.get("source_type") or "source"
                quote = citation.get("quote")
                suffix = f"：{quote}" if quote else ""
                lines.append(f"- [{source_type}] {title}{suffix}")
        return "\n".join(lines) if lines else "- AI 推断内容，建议核对资料。"
