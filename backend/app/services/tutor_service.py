from __future__ import annotations

from collections.abc import AsyncIterator
from time import perf_counter
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context import AgentContext
from app.agents.tutor_agent import TutorAgent
from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.llm import ChatMessage, get_llm_provider
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
from app.services.agent_service import AgentService
from app.services.agent_log_service import AgentLogService
from app.services.course_service import CourseService
from app.services.learning_record_service import LearningRecordService


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
        course = await self._get_accessible_course(payload.course_id, current_user)
        if payload.wiki_page_id is not None:
            await self._get_readable_wiki_page(payload.wiki_page_id, course, current_user)

        result = await AgentService(self.db).run_task(
            task_type="course_qa",
            user_id=current_user.id,
            course_id=course.id,
            params=payload.model_dump(mode="json"),
        )
        if not result.success:
            raise BusinessException(
                code=ErrorCode.AGENT_RUN_FAILED,
                detail=result.message,
                status_code=500,
            )

        data = result.data
        answer = str(data.get("answer") or "").strip()
        if not answer:
            raise BusinessException(
                code=ErrorCode.LLM_CALL_FAILED,
                detail="Tutor 回答为空",
                status_code=500,
            )

        review_result = await self._review_answer(
            user_id=current_user.id,
            course_id=course.id,
            answer=answer,
            citations=data.get("citations") or [],
        )

        record = await self.records.record_event(
            user_id=current_user.id,
            course_id=course.id,
            knowledge_id=payload.knowledge_id,
            event_type="chat",
            event_source="tutor",
            event_payload={
                "question": payload.question,
                "answer": answer,
                "citations": data.get("citations") or [],
                "related_knowledge_points": data.get("related_knowledge_points") or [],
                "follow_up_questions": data.get("follow_up_questions") or [],
                "save_to_wiki_candidate": data.get("save_to_wiki_candidate"),
                "agent_run_id": data.get("agent_run_id"),
                "review_result": review_result,
                "model": data.get("model"),
                "provider": data.get("provider"),
                "fallback_used": data.get("fallback_used"),
                "failed_provider": data.get("failed_provider"),
                "fallback_reason": data.get("fallback_reason"),
            },
        )

        response_payload = {
            "answer": answer,
            "citations": data.get("citations") or [],
            "related_knowledge_points": data.get("related_knowledge_points") or [],
            "follow_up_questions": data.get("follow_up_questions") or [],
            "save_to_wiki_candidate": data.get("save_to_wiki_candidate"),
            "agent_run_id": data.get("agent_run_id"),
            "review_result": review_result,
            "memory_update_suggestion": data.get("memory_update_suggestion") or {},
            "message_id": record.id,
            "model": data.get("model"),
            "provider": data.get("provider"),
            "fallback_used": bool(data.get("fallback_used")),
            "failed_provider": data.get("failed_provider"),
            "fallback_reason": data.get("fallback_reason"),
        }
        return TutorChatResponse.model_validate(response_payload)

    async def stream_chat(
        self,
        *,
        payload: TutorChatRequest,
        current_user: User,
    ) -> AsyncIterator[dict[str, Any]]:
        yield {"event": "progress", "data": {"stage": "retrieve_context", "message": "检索课程资料与 Wiki"}}
        course = await self._get_accessible_course(payload.course_id, current_user)
        if payload.wiki_page_id is not None:
            await self._get_readable_wiki_page(payload.wiki_page_id, course, current_user)

        log_service = AgentLogService(self.db)
        context = AgentContext(
            user_id=current_user.id,
            course_id=course.id,
            task_type="course_qa",
            params=payload.model_dump(mode="json"),
        )
        run_log = await log_service.start_run(
            task_type=context.task_type,
            agent_name=TutorAgent.name,
            input_payload={"params": context.params, "metadata": context.metadata},
            user_id=context.user_id,
            course_id=context.course_id,
        )
        context.run_id = run_log.id
        started = perf_counter()

        try:
            yield {"event": "progress", "data": {"stage": "build_profile_context", "message": "整理学生画像上下文"}}
            agent = TutorAgent(self.db)
            prepared = await agent.prepare_chat_context(context)

            yield {"event": "progress", "data": {"stage": "llm_generation", "message": "Tutor Agent 流式调用真实 LLM"}}
            llm = get_llm_provider(
                db=self.db,
                user_id=current_user.id,
                course_id=course.id,
                agent_run_id=context.run_id,
                prompt_version_id=prepared["prompt_version_id"],
            )
            chunks: list[str] = []
            async for chunk in llm.stream_chat(
                [ChatMessage(role="user", content=prepared["prompt"])],
                temperature=0.7,
                max_tokens=2048,
                prompt_version_id=prepared["prompt_version_id"],
            ):
                if not chunk:
                    continue
                chunks.append(chunk)
                yield {"event": "delta", "data": {"content": chunk}}

            answer = agent.finalize_answer("".join(chunks), prepared["citations"])
            if not answer:
                raise BusinessException(
                    code=ErrorCode.LLM_CALL_FAILED,
                    detail="Tutor 回答为空",
                    status_code=500,
                )

            yield {"event": "progress", "data": {"stage": "review", "message": "Review Agent 校验回答依据"}}
            review_result = await self._review_answer(
                user_id=current_user.id,
                course_id=course.id,
                answer=answer,
                citations=prepared["citations"],
            )
            record = await self.records.record_event(
                user_id=current_user.id,
                course_id=course.id,
                knowledge_id=payload.knowledge_id,
                event_type="chat",
                event_source="tutor",
                event_payload={
                    "question": payload.question,
                    "answer": answer,
                    "citations": prepared["citations"],
                    "related_knowledge_points": prepared["related_knowledge_points"],
                    "follow_up_questions": prepared["follow_up_questions"],
                    "save_to_wiki_candidate": agent._save_candidate(prepared["question"], answer),
                    "agent_run_id": str(context.run_id) if context.run_id else None,
                    "review_result": review_result,
                    "model": self._stream_model_name(llm),
                    "provider": self._stream_provider_name(llm),
                    "fallback_used": False,
                    "failed_provider": None,
                    "fallback_reason": None,
                },
                commit=False,
            )
            response_payload = {
                "answer": answer,
                "citations": prepared["citations"],
                "related_knowledge_points": prepared["related_knowledge_points"],
                "follow_up_questions": prepared["follow_up_questions"],
                "save_to_wiki_candidate": agent._save_candidate(prepared["question"], answer),
                "agent_run_id": context.run_id,
                "review_result": review_result,
                "memory_update_suggestion": {
                    "should_reflect": True,
                    "reason": "本次问答可作为学生关注知识点和解释偏好的证据。",
                },
                "message_id": record.id,
                "model": self._stream_model_name(llm),
                "provider": self._stream_provider_name(llm),
                "fallback_used": False,
                "failed_provider": None,
                "fallback_reason": None,
            }
            await log_service.finish_run(
                run_id=run_log.id,
                output_payload=TutorChatResponse.model_validate(response_payload).model_dump(mode="json"),
                status="success",
                duration_ms=int((perf_counter() - started) * 1000),
                error_message=None,
            )
            await self.db.commit()
            await self.db.refresh(record)
            yield {
                "event": "done",
                "data": TutorChatResponse.model_validate(response_payload).model_dump(mode="json"),
            }
        except Exception as exc:
            await log_service.finish_run(
                run_id=run_log.id,
                output_payload={},
                status="failed",
                duration_ms=int((perf_counter() - started) * 1000),
                error_message=str(exc),
            )
            await self.db.commit()
            raise

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

    async def _review_answer(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        answer: str,
        citations: list[Any],
    ) -> dict[str, Any]:
        review = await AgentService(self.db).run_task(
            task_type="review_content",
            user_id=user_id,
            course_id=course_id,
            params={
                "content": (
                    f"{answer[:3500]}\n\n"
                    f"引用来源数量：{len(citations)}；引用来源：{citations[:5]}"
                )
            },
        )
        if review.success:
            return review.data
        return {
            "pass": bool(citations),
            "risk_level": "medium",
            "issues": [review.message],
            "revision_suggestions": "Review Agent 未完成，已按引用数量做规则兜底。",
        }

    async def _get_accessible_course(self, course_id: UUID, current_user: User) -> Course:
        return await CourseService(self.db).get_readable_course(course_id, current_user)

    def _stream_provider_name(self, llm: object) -> str:
        inner = getattr(llm, "inner", llm)
        return str(getattr(inner, "provider_name", getattr(llm, "provider_name", "unknown")))

    def _stream_model_name(self, llm: object) -> str | None:
        inner = getattr(llm, "inner", llm)
        return getattr(inner, "_model", None)

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
