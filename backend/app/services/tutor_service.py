from __future__ import annotations

import logging
import re
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
from app.repositories.agent_conversation_repository import AgentConversationRepository
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
from app.services.conversation_context_service import ConversationContext, ConversationContextService
from app.services.conversation_summary_service import ConversationSummaryService
from app.services.grounded_qa_pipeline import GroundedQaPipeline
from app.services.learning_record_service import LearningRecordService
from app.services.tutor_request_service import TutorClaim, TutorRequestService


logger = logging.getLogger(__name__)


VALID_FEEDBACK_TYPES = {"like", "dislike", "useful", "useless", "report_error"}


class TutorService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.courses = CourseRepository(db)
        self.wiki = WikiRepository(db)
        self.feedback = FeedbackRepository(db)
        self.records = LearningRecordService(db)
        self.conversations = AgentConversationRepository(db)

    async def chat(
        self,
        *,
        payload: TutorChatRequest,
        current_user: User,
    ) -> TutorChatResponse:
        if payload.client_request_id is not None and payload.conversation_id is not None:
            await self._get_accessible_course(payload.course_id, current_user)
        requests = TutorRequestService(self.db)
        claim = await requests.claim(payload, current_user.id)
        if claim is not None and claim.completed is not None:
            return claim.completed
        try:
            response = await self._chat_unclaimed(payload=payload, current_user=current_user, claim=claim)
            await requests.complete(claim, response)
            await self._maybe_compact(response.conversation_id, current_user.id)
            return response
        except Exception as exc:
            await requests.fail(claim, exc)
            raise

    async def _chat_unclaimed(
        self, *, payload: TutorChatRequest, current_user: User, claim: TutorClaim | None = None,
    ) -> TutorChatResponse:
        from app.agent_runtime import supervisor_intents

        if (supervisor_intents.web_search_intent(payload.question)
                or ConversationContext.requested_web_ordinal(payload.question) is not None
                or ConversationContext.requested_quiz_option(payload.question) is not None
                or ConversationContext.requested_material_reference(payload.question)):
            course = await self._get_accessible_course(payload.course_id, current_user)
            if payload.wiki_page_id is not None:
                await self._get_readable_wiki_page(payload.wiki_page_id, course, current_user)
            async for event in self._stream_reference_or_search_answer(
                payload=payload,
                current_user=current_user,
                course=course,
                claim=claim,
            ):
                if event.get("event") == "done":
                    return TutorChatResponse.model_validate(event.get("data") or {})
            raise BusinessException(
                code=ErrorCode.LLM_CALL_FAILED,
                detail="联网问答未返回结果",
                status_code=500,
            )
        pipeline = GroundedQaPipeline(self.db) if claim is None else GroundedQaPipeline(self.db, request_claim=claim)
        return await pipeline.answer(payload, current_user)

    async def stream_chat(
        self,
        *,
        payload: TutorChatRequest,
        current_user: User,
    ) -> AsyncIterator[dict[str, Any]]:
        if payload.client_request_id is not None and payload.conversation_id is not None:
            await self._get_accessible_course(payload.course_id, current_user)
        requests = TutorRequestService(self.db)
        claim = await requests.claim(payload, current_user.id)
        if claim is not None and claim.completed is not None:
            yield {"event": "done", "data": claim.completed.model_dump(mode="json")}
            return
        try:
            completed: TutorChatResponse | None = None
            async for item in self._stream_chat_unclaimed(payload=payload, current_user=current_user, claim=claim):
                if item.get("event") == "done":
                    completed = TutorChatResponse.model_validate(item.get("data") or {})
                    await requests.complete(claim, completed)
                    await self._maybe_compact(completed.conversation_id, current_user.id)
                yield item
            if completed is None:
                raise RuntimeError("Tutor 流式回答没有完成事件")
        except BaseException as exc:
            await requests.fail(claim, exc if isinstance(exc, Exception) else RuntimeError("连接已中断"))
            raise

    async def _stream_chat_unclaimed(
        self, *, payload: TutorChatRequest, current_user: User, claim: TutorClaim | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        from app.agent_runtime import supervisor_intents

        if (supervisor_intents.web_search_intent(payload.question)
                or ConversationContext.requested_web_ordinal(payload.question) is not None
                or ConversationContext.requested_quiz_option(payload.question) is not None
                or ConversationContext.requested_material_reference(payload.question)):
            course = await self._get_accessible_course(payload.course_id, current_user)
            if payload.wiki_page_id is not None:
                await self._get_readable_wiki_page(payload.wiki_page_id, course, current_user)
            async for item in self._stream_reference_or_search_answer(
                payload=payload,
                current_user=current_user,
                course=course,
                claim=claim,
            ):
                yield item
            return
        pipeline = GroundedQaPipeline(self.db) if claim is None else GroundedQaPipeline(self.db, request_claim=claim)
        async for event in pipeline.stream(payload, current_user):
            yield event

    async def _maybe_compact(self, conversation_id: UUID | None, user_id: UUID) -> None:
        if conversation_id is None or not callable(getattr(self.db, "execute", None)):
            return
        try:
            await ConversationSummaryService(self.db).maybe_compact(
                conversation_id=conversation_id, user_id=user_id,
            )
        except Exception:
            await self.db.rollback()
            logger.exception("conversation compaction failed; committed answer remains available")

    async def _stream_reference_or_search_answer(
        self,
        *,
        payload: TutorChatRequest,
        current_user: User,
        course: Course,
        claim: TutorClaim | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        from app.agent_runtime.supervisor import MiMoSupervisor
        from app.services.web_search_service import WebSearchService

        requested_ordinal = ConversationContext.requested_web_ordinal(payload.question)
        requested_option = ConversationContext.requested_quiz_option(payload.question)
        requested_material = ConversationContext.requested_material_reference(payload.question)
        yield {"event": "progress", "data": {
            "stage": "read_quiz_question" if requested_option is not None else "read_material" if requested_material else "read_web_page" if requested_ordinal is not None else "web_search",
            "message": "正在核对上一道题…" if requested_option is not None else "正在核对会话资料…" if requested_material else "正在读取已引用的网页…" if requested_ordinal is not None else "联网搜索中…",
        }}
        context = await ConversationContextService(self.db).load(
            conversation_id=payload.conversation_id,
            user_id=current_user.id,
            course_id=course.id,
        )
        ordinal = requested_ordinal
        if requested_option is not None:
            answer, citations, provider_name = await self._answer_quiz_option(
                context=context, payload=payload, current_user=current_user, course=course,
            )
            result = {"provider": provider_name}
        elif requested_material:
            answer, citations, provider_name = await self._answer_material_reference(
                context=context, payload=payload, current_user=current_user, course=course,
            )
            result = {"provider": provider_name}
        elif ordinal is not None:
            answer, citations, provider_name = await self._answer_web_reference(
                context=context, payload=payload, current_user=current_user, course=course,
            )
            result = {"provider": provider_name}
        else:
            query = context.resolve_query(payload.question)
            result = await WebSearchService().search(query=query, max_results=5)
            answer = MiMoSupervisor(provider=object())._format_search_output_answer(  # type: ignore[arg-type]
                "search_web", result, query,
            )
            citations = list(result.get("citations") or [])
        chunk_size = 120
        for index in range(0, len(answer), chunk_size):
            yield {"event": "delta", "data": {"content": answer[index : index + chunk_size]}}

        if claim is not None and payload.conversation_id is not None:
            await self.conversations.get_for_user_locked(payload.conversation_id, current_user.id)
        await TutorRequestService(self.db).assert_owner(claim)
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
            commit=False,
        )
        response_payload = {
            "answer": answer,
            "citations": citations,
            "related_knowledge_points": [],
            "follow_up_questions": [],
            "review_result": review_result,
            "memory_update_suggestion": {"should_reflect": False, "reason": "对象引用问答不写入长期记忆。"},
            "message_id": str(record.id),
            "provider": result.get("provider") or "anysearch",
            "fallback_used": result.get("provider") == "mock",
            "grounding_status": "grounded" if (ordinal is not None or requested_option is not None or requested_material) and citations else "partial" if citations else "insufficient",
            "grounding_message": (
                "依据已核验的练习题与选项。" if requested_option is not None and citations
                else "无法定位或核验上一道题的选项。" if requested_option is not None
                else "依据当前会话引用的资料片段。" if requested_material and citations
                else "无法唯一定位或读取当前会话的资料。" if requested_material
                else
                "依据已读取的网页正文。" if ordinal is not None and citations
                else "这是联网搜索结果，尚未读取网页正文。" if citations
                else "未找到可读取的网页依据。"
            ),
        }
        if payload.conversation_id is not None:
            conversation = await self.conversations.get_for_user(payload.conversation_id, current_user.id)
            if conversation is None or conversation.course_id != course.id:
                raise BusinessException(code=ErrorCode.NOT_FOUND, detail="当前课程的会话不存在", status_code=404)
        else:
            conversation = await self.conversations.create(
                user_id=current_user.id,
                course_id=course.id,
                title=payload.question[:80],
            )
        await self.conversations.add_message(
            conversation=conversation,
            user_id=current_user.id,
            role="user",
            content=payload.question,
            payload={"client_request_id": str(payload.client_request_id) if payload.client_request_id else None},
        )
        response_payload["conversation_id"] = str(conversation.id)
        await self.conversations.add_message(
            conversation=conversation,
            user_id=current_user.id,
            role="assistant",
            content=answer,
            message_type="tutor",
            client_request_id=payload.client_request_id,
            payload={**response_payload, "learning_record_id": str(record.id)},
        )
        await self.db.commit()
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

    async def _answer_web_reference(
        self, *, context: ConversationContext, payload: TutorChatRequest,
        current_user: User, course: Course,
    ) -> tuple[str, list[dict[str, Any]], str]:
        from app.llm.provider import get_llm_provider
        from app.services.prompt_service import PromptService
        from app.services.web_search_service import WebSearchService

        ordinal = ConversationContext.requested_web_ordinal(payload.question)
        reference = context.resolve_web_reference(payload.question)
        if reference is None:
            return (
                f"当前会话无法确定第 {ordinal} 个网页链接。请先联网搜索，并指出要阅读的结果序号。",
                [], "rule",
            )
        try:
            page = await WebSearchService().extract_page(url=reference["url"])
        except Exception:
            logger.exception("failed to read cited web page")
            page = {"content": "", "provider": "anysearch"}
        content = str(page.get("content") or "").strip()
        if not content or page.get("provider") == "mock":
            return (
                f"已找到第 {ordinal} 个链接「{reference['title']}」，但目前无法读取网页正文，因此不能可靠总结。来源：{reference['url']}",
                [], str(page.get("provider") or "anysearch"),
            )
        citation = {
            "source_type": "web", "title": reference["title"],
            "url": reference["url"], "quote": content[:300],
        }
        from app.core.config import settings

        if settings.llm_provider == "mock" or not settings.llm_api_key:
            return (
                f"已读取「{reference['title']}」。以下是网页正文摘录（Mock 模式未生成 AI 摘要）：\n\n{content[:800]}",
                [citation], "extractive",
            )
        rendered = await PromptService(self.db).render_prompt(
            agent_name="TutorAgent", scene="tutor.web_reference",
            params={
                "question": payload.question, "title": reference["title"],
                "url": reference["url"], "content": content[:12000],
            },
        )
        provider = get_llm_provider(
            db=self.db, user_id=current_user.id, course_id=course.id,
            prompt_version_id=rendered.prompt_version_id,
        )
        llm_response = await provider.chat(
            context.messages_for(rendered.content), temperature=0.2, max_tokens=1200,
            thinking={"type": "disabled"}, prompt_version_id=rendered.prompt_version_id,
        )
        if bool((getattr(llm_response, "raw", None) or {}).get("fallback_used")):
            return (
                f"已读取「{reference['title']}」。模型生成失败，以下是网页正文摘录：\n\n{content[:800]}",
                [citation], "extractive",
            )
        answer = str(llm_response.content or "").strip() or "网页正文已读取，但本轮未能生成可靠摘要。"
        return answer, [citation], getattr(llm_response, "provider", None) or "llm"

    async def _answer_quiz_option(
        self, *, context: ConversationContext, payload: TutorChatRequest,
        current_user: User, course: Course,
    ) -> tuple[str, list[dict[str, Any]], str]:
        from uuid import UUID

        from app.core.config import settings
        from app.llm.provider import get_llm_provider
        from app.repositories.quiz_repository import QuizRepository
        from app.services.prompt_service import PromptService

        option_no = ConversationContext.requested_quiz_option(payload.question)
        reference = context.quiz_reference
        if option_no is None or not reference:
            return "当前会话找不到可核验的上一道练习题，请指出具体题目。", [], "rule"
        try:
            quiz_id = UUID(reference["id"])
        except (KeyError, ValueError):
            return "上一道练习题的引用无效，请指出具体题目。", [], "rule"
        quiz = await QuizRepository(self.db).get_quiz_for_user(quiz_id=quiz_id, user_id=current_user.id)
        if quiz is None or quiz.course_id != course.id:
            return "当前课程找不到可访问的上一道练习题。", [], "rule"
        question_no = ConversationContext.requested_quiz_question(payload.question)
        if question_no is not None:
            matching = [item for item in quiz.questions if getattr(item, "position", None) == question_no]
            if len(matching) != 1:
                return "无法核验该题号（历史题组可能未记录顺序），请贴出具体题干。", [], "rule"
            question = matching[0]
        elif len(quiz.questions) == 1:
            question = quiz.questions[0]
        else:
            return "这组练习包含多道题。请指定题号和选项，例如第二题选项B；历史题组请贴出题干。", [], "rule"
        options = question.options
        if isinstance(options, dict):
            label = chr(ord("A") + option_no - 1) if 1 <= option_no <= 26 else ""
            option_text = f"{label}：{options[label]}" if label in options else ""
        elif isinstance(options, list):
            selected = options[option_no - 1] if 1 <= option_no <= len(options) else None
            option_text = str(selected) if selected is not None else ""
        else:
            option_text = ""
        if not option_text:
            return f"上一道题没有第 {option_no} 个可核验的选项。", [], "rule"
        citation = {
            "source_type": "quiz", "title": quiz.title,
            "source_id": str(question.id), "quote": f"{question.question_text[:180]}；{option_text[:180]}",
        }
        if settings.llm_provider == "mock" or not settings.llm_api_key:
            return (
                f"题干：{question.question_text}\n第 {option_no} 个选项：{option_text}\n"
                f"标准答案：{question.standard_answer}\n"
                f"已有解析：{question.analysis or '题目未提供解析，Mock 模式不推断原因。'}",
                [citation], "extractive",
            )
        rendered = await PromptService(self.db).render_prompt(
            agent_name="TutorAgent", scene="tutor.quiz_option",
            params={
                "question": payload.question, "stem": question.question_text[:3000],
                "option": option_text[:1000], "answer": question.standard_answer[:1000],
                "analysis": (question.analysis or "未提供")[:3000],
            },
        )
        provider = get_llm_provider(
            db=self.db, user_id=current_user.id, course_id=course.id,
            prompt_version_id=rendered.prompt_version_id,
        )
        response = await provider.chat(
            context.messages_for(rendered.content), temperature=0.2, max_tokens=1000,
            thinking={"type": "disabled"}, prompt_version_id=rendered.prompt_version_id,
        )
        if bool((getattr(response, "raw", None) or {}).get("fallback_used")):
            return f"模型生成失败。题干：{question.question_text}\n选项：{option_text}\n已有解析：{question.analysis or '未提供'}", [citation], "extractive"
        return str(response.content or "").strip() or "这道题暂无可靠解释。", [citation], getattr(response, "provider", None) or "llm"

    async def _answer_material_reference(
        self, *, context: ConversationContext, payload: TutorChatRequest,
        current_user: User, course: Course,
    ) -> tuple[str, list[dict[str, Any]], str]:
        from uuid import UUID

        from app.core.config import settings
        from app.core.exceptions import BusinessException
        from app.llm.provider import get_llm_provider
        from app.repositories.chunk_repository import ChunkRepository
        from app.services.material_service import MaterialService
        from app.services.prompt_service import PromptService

        references = context.material_references
        if not references:
            return "当前会话没有可核验的资料引用。请指定资料名称或先在会话中引用该资料。", [], "rule"
        reference = context.resolve_material_reference(payload.question)
        if reference is None:
            return "刚才引用了多份资料或指定序号无效，无法唯一定位。请指定资料名称或序号，例如第二份资料。", [], "rule"
        try:
            material_id = UUID(str(reference["id"]))
            material = await MaterialService(self.db).get_readable_material(material_id, current_user)
        except (KeyError, ValueError, BusinessException):
            return "当前课程找不到可访问的这份资料。", [], "rule"
        if material.course_id != course.id:
            return "当前课程找不到可访问的这份资料。", [], "rule"
        chunks_repo = ChunkRepository(self.db)
        if re.search(r"总结|摘要|概括|梳理整|全文", payload.question):
            from app.services.material_summary_service import MaterialSummaryService, source_batches

            all_chunks = await chunks_repo.list_by_material(material_id)
            all_chunks = [item for item in all_chunks if item.course_id == course.id]
            try:
                batches = source_batches(all_chunks)
            except ValueError:
                return "资料超过本轮同步摘要预算，请按章节拆分后总结；本轮未生成全文摘要。", [], "rule"
            if not batches:
                return "这份资料尚无可读取的解析正文。", [], "rule"
            if settings.llm_provider == "mock" or not settings.llm_api_key:
                return f"Mock 模式：已读取 {len(all_chunks)} 个切片，未调用真实模型生成全文摘要。\n\n{batches[0][:2000]}", [], "extractive"
            provider = get_llm_provider(db=self.db, user_id=current_user.id, course_id=course.id, allow_mock_fallback=False)
            answer = await MaterialSummaryService(self.db).summarize(chunks=all_chunks, title=material.file_name,
                question=payload.question, provider=provider)
            citations = [{"source_type": "document", "title": material.file_name, "source_id": str(material_id),
                          "chunk_id": str(item.id), "page_no": item.page_no, "quote": str(item.content or "")[:200]}
                         for item in all_chunks]
            return answer, citations, provider.provider_name
        chunk_ids = list(reference.get("chunk_ids") or [])[:5]
        chunks = []
        for chunk_id in chunk_ids:
            try:
                chunk = await chunks_repo.get_by_id(UUID(str(chunk_id)))
            except ValueError:
                continue
            if chunk is not None and chunk.material_id == material_id and chunk.course_id == course.id:
                chunks.append(chunk)
        from_citations = bool(chunks)
        if not chunks:
            chunks = await chunks_repo.list_preview_by_material(material_id, limit=5)
            chunks = [item for item in chunks if item.course_id == course.id]
        if not chunks:
            return f"已定位资料「{material.file_name}」，但没有可读取的切片，暂时无法依据正文回答。", [], "rule"
        scope = "本轮只覆盖上次回答引用的片段" if from_citations else "本轮只覆盖资料开头的部分切片"
        citations = [
            {
                "source_type": "document", "title": material.file_name,
                "source_id": str(material_id), "chunk_id": str(chunk.id),
                "page_no": chunk.page_no, "quote": str(chunk.content or "")[:500],
            }
            for chunk in chunks
        ]
        excerpts = "\n\n".join(
            f"片段 {index}：{str(chunk.content or '')[:1200]}"
            for index, chunk in enumerate(chunks, start=1)
        )
        if settings.llm_provider == "mock" or not settings.llm_api_key:
            return f"已定位资料「{material.file_name}」。{scope}；Mock 模式不生成整份资料的摘要。\n\n{excerpts[:3000]}", citations, "extractive"
        rendered = await PromptService(self.db).render_prompt(
            agent_name="TutorAgent", scene="tutor.material_reference",
            params={
                "question": payload.question, "title": material.file_name,
                "scope": scope, "excerpts": excerpts[:6500],
            },
        )
        provider = get_llm_provider(
            db=self.db, user_id=current_user.id, course_id=course.id,
            prompt_version_id=rendered.prompt_version_id,
        )
        response = await provider.chat(
            context.messages_for(rendered.content), temperature=0.2, max_tokens=1200,
            thinking={"type": "disabled"}, prompt_version_id=rendered.prompt_version_id,
        )
        if bool((getattr(response, "raw", None) or {}).get("fallback_used")):
            return f"模型生成失败。{scope}，以下为可核验片段：\n\n{excerpts[:3000]}", citations, "extractive"
        answer = str(response.content or "").strip() or "资料片段已读取，但本轮未能生成可靠回答。"
        return f"{scope}。\n\n{answer}", citations, getattr(response, "provider", None) or "llm"

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
