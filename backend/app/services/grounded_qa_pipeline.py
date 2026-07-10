from __future__ import annotations

import json
from time import perf_counter
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm import ChatMessage, get_llm_provider
from app.models.course import Course
from app.models.user import User
from app.rag.evidence import (
    CitationValidationResult,
    EvidenceBundle,
    EvidenceItem,
    GraphContext,
)
from app.repositories.agent_conversation_repository import AgentConversationRepository
from app.schemas.tutor import (
    RelatedKnowledgePoint,
    TutorChatRequest,
    TutorChatResponse,
    TutorPerformance,
)
from app.services.agent_log_service import AgentLogService
from app.services.citation_validator import CitationValidator
from app.services.conversation_intent import is_simple_greeting, simple_greeting_answer
from app.services.course_service import CourseService
from app.services.evidence_retrieval_service import EvidenceRetrievalService
from app.services.learning_record_service import LearningRecordService
from app.services.personalization_context_service import PersonalizationContextService
from app.services.prompt_service import PromptService


class GroundedQaPipeline:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.retrieval = EvidenceRetrievalService(db)
        self.validator = CitationValidator()
        self.records = LearningRecordService(db)
        self.conversations = AgentConversationRepository(db)
        self.logs = AgentLogService(db)
        self._agent_run_id: UUID | None = None

    async def answer(
        self,
        payload: TutorChatRequest,
        current_user: User,
        *,
        persist_conversation_messages: bool = True,
        agent_run_id: UUID | None = None,
    ) -> TutorChatResponse:
        started = perf_counter()
        course = await self._authorize(payload, current_user)
        if is_simple_greeting(payload.question):
            return await self._answer_greeting(
                payload=payload,
                current_user=current_user,
                course=course,
                persist_conversation_messages=persist_conversation_messages,
                started=started,
                agent_run_id=agent_run_id,
            )

        manages_run = agent_run_id is None
        if manages_run:
            run = await self.logs.start_run(
                task_type="course_qa",
                agent_name="TutorAgent",
                input_payload={"params": payload.model_dump(mode="json")},
                user_id=current_user.id,
                course_id=course.id,
            )
            agent_run_id = run.id
        self._agent_run_id = agent_run_id
        try:
            retrieval_started = perf_counter()
            bundle = await self._retrieve(payload, current_user)
            retrieval_ms = int((perf_counter() - retrieval_started) * 1000)
            provider, prompt, prompt_version_id = await self._build_generation(
                bundle, payload, current_user
            )
            generation_started = perf_counter()
            llm_response = await provider.chat(
                [ChatMessage(role="user", content=prompt)],
                temperature=0.2,
                max_tokens=1200,
                thinking={"type": "disabled"},
                prompt_version_id=prompt_version_id,
            )
            answer = llm_response.content.strip()
            validated = self.validator.validate(answer, bundle.evidence)
            if validated.unknown_keys:
                for key in validated.unknown_keys:
                    answer = answer.replace(f"[{key}]", "")
                answer = answer.strip()
                if bundle.evidence:
                    validated = CitationValidationResult(
                        citations=validated.citations,
                        unknown_keys=validated.unknown_keys,
                        grounding_status="partial",
                        grounding_message="回答中的未知引用编号已移除，部分内容需核对课程资料。",
                    )
            performance = TutorPerformance(
                retrieval_ms=retrieval_ms,
                first_token_ms=None,
                generation_ms=int((perf_counter() - generation_started) * 1000),
                total_ms=int((perf_counter() - started) * 1000),
                llm_call_count=1,
                evidence_candidate_count=bundle.candidate_count,
                evidence_accepted_count=len(bundle.evidence),
            )
            response = self._build_response(
                answer=answer,
                validation=validated,
                bundle=bundle,
                payload=payload,
                llm_response=llm_response,
                performance=performance,
            ).model_copy(update={"agent_run_id": agent_run_id})
            message_id, conversation_id = await self._persist(
                response=response,
                payload=payload,
                current_user=current_user,
                course=course,
                persist_conversation_messages=persist_conversation_messages,
            )
            response = response.model_copy(
                update={
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "postprocess_status": "queued" if message_id else "skipped",
                }
            )
            if manages_run and agent_run_id is not None:
                await self.logs.finish_run(
                    run_id=agent_run_id,
                    output_payload={
                        **response.model_dump(mode="json"),
                        "evidence_candidate_count": bundle.candidate_count,
                        "evidence_accepted_count": len(bundle.evidence),
                        "grounding_status": validated.grounding_status,
                    },
                    status="success",
                    duration_ms=int((perf_counter() - started) * 1000),
                    error_message=None,
                )
            return response
        except Exception as exc:
            if manages_run and agent_run_id is not None:
                await self.logs.finish_run(
                    run_id=agent_run_id,
                    output_payload={},
                    status="failed",
                    duration_ms=int((perf_counter() - started) * 1000),
                    error_message=str(exc),
                )
            raise
        finally:
            self._agent_run_id = None

    async def _answer_greeting(
        self,
        *,
        payload: TutorChatRequest,
        current_user: User,
        course: Course,
        persist_conversation_messages: bool,
        started: float,
        agent_run_id: UUID | None,
    ) -> TutorChatResponse:
        response = TutorChatResponse(
            answer=simple_greeting_answer(),
            provider="local_intent_router",
            agent_run_id=agent_run_id,
            review_result={
                "pass": True,
                "risk_level": "low",
                "reviewer": "local_intent_router",
            },
            memory_update_suggestion={
                "should_reflect": False,
                "reason": "简单寒暄不写入长期学习记忆。",
            },
            performance=TutorPerformance(
                total_ms=int((perf_counter() - started) * 1000),
                llm_call_count=0,
            ),
        )
        message_id, conversation_id = await self._persist(
            response=response,
            payload=payload,
            current_user=current_user,
            course=course,
            persist_conversation_messages=persist_conversation_messages,
        )
        return response.model_copy(
            update={
                "message_id": message_id,
                "conversation_id": conversation_id,
                "postprocess_status": "queued" if message_id else "skipped",
            }
        )

    async def _authorize(
        self,
        payload: TutorChatRequest,
        current_user: User,
    ) -> Course:
        return await CourseService(self.db).get_readable_course(
            payload.course_id, current_user
        )

    async def _retrieve(
        self,
        payload: TutorChatRequest,
        current_user: User,
    ) -> EvidenceBundle:
        return await self.retrieval.retrieve(
            course_id=payload.course_id,
            user_id=current_user.id,
            question=payload.question,
            top_k=payload.top_k,
            knowledge_id=payload.knowledge_id,
            wiki_page_id=payload.wiki_page_id,
            use_rag=payload.use_rag,
            use_wiki=payload.use_wiki,
        )

    async def _build_generation(
        self,
        bundle: EvidenceBundle,
        payload: TutorChatRequest,
        current_user: User,
    ) -> tuple[object, str, UUID | None]:
        if payload.use_profile:
            personalization = await PersonalizationContextService(self.db).get_context(
                current_user.id, payload.course_id
            )
            student_profile = PersonalizationContextService.format_profile_for_prompt(
                personalization
            )
            memory_context = PersonalizationContextService.format_memories_for_prompt(
                personalization
            )
        else:
            student_profile = "未启用学生画像"
            memory_context = "未启用长期记忆"

        retrieved_context = self._format_evidence(bundle.evidence)
        rendered = await PromptService(self.db).render_grounded_tutor_prompt(
            {
                "question": payload.question,
                "retrieved_context": retrieved_context[:6000],
                "wiki_context": retrieved_context[:6000],
                "graph_context": self._format_graph_context(bundle.graph_context)[:2000],
                "student_profile": student_profile[:1600],
                "memory_context": memory_context[:1600],
            }
        )
        provider = get_llm_provider(
            db=self.db,
            user_id=current_user.id,
            course_id=payload.course_id,
            agent_run_id=self._agent_run_id,
            prompt_version_id=rendered.prompt_version_id,
        )
        return provider, rendered.content, rendered.prompt_version_id

    def _build_response(
        self,
        *,
        answer: str,
        validation: CitationValidationResult,
        bundle: EvidenceBundle,
        payload: TutorChatRequest,
        llm_response: object,
        performance: TutorPerformance,
    ) -> TutorChatResponse:
        raw = getattr(llm_response, "raw", None) or {}
        related = self._related_knowledge_points(bundle.evidence)
        return TutorChatResponse(
            answer=answer,
            citations=[item.as_citation() for item in validation.citations],
            related_knowledge_points=related,
            follow_up_questions=self._follow_up_questions(related),
            save_to_wiki_candidate=self._save_candidate(payload.question, answer),
            review_result={
                "pass": validation.grounding_status == "grounded",
                "risk_level": (
                    "low" if validation.grounding_status == "grounded" else "medium"
                ),
                "issues": [f"未知引用编号：{key}" for key in validation.unknown_keys],
                "reviewer": "citation_validator",
            },
            memory_update_suggestion={
                "should_reflect": True,
                "reason": "本次问答可作为学生关注知识点和解释偏好的证据。",
            },
            model=getattr(llm_response, "model", None),
            provider=getattr(llm_response, "provider", None),
            fallback_used=bool(raw.get("fallback_used")),
            failed_provider=raw.get("failed_provider"),
            fallback_reason=raw.get("fallback_reason"),
            graph_context=self._graph_context_payload(bundle.graph_context),
            grounding_status=validation.grounding_status,
            grounding_message=validation.grounding_message,
            performance=performance,
        )

    async def _persist(
        self,
        *,
        response: TutorChatResponse,
        payload: TutorChatRequest,
        current_user: User,
        course: Course,
        persist_conversation_messages: bool,
    ) -> tuple[UUID | None, UUID | None]:
        del response, current_user, course, persist_conversation_messages
        return None, payload.conversation_id

    def _format_evidence(self, evidence: list[EvidenceItem]) -> str:
        if not evidence:
            return "课程资料未找到可靠依据。"
        blocks = []
        for item in evidence:
            page = str(item.page_no) if item.page_no is not None else "未标注"
            blocks.append(
                f"[{item.citation_key}] 标题：{item.title}\n页码：{page}\n原文：{item.quote}"
            )
        return "\n\n".join(blocks)

    def _format_graph_context(self, graph: GraphContext) -> str:
        if (
            not graph.seed_knowledge_ids
            and not graph.expanded_knowledge_ids
            and not graph.relation_paths
        ):
            return "未检索到可用知识关系。"
        return (
            f"种子知识点：{', '.join(map(str, graph.seed_knowledge_ids)) or '无'}\n"
            f"扩展知识点：{', '.join(map(str, graph.expanded_knowledge_ids)) or '无'}\n"
            f"关系路径：{json.dumps(graph.relation_paths, ensure_ascii=False, default=str)}"
        )

    def _graph_context_payload(self, graph: GraphContext) -> dict[str, Any]:
        return {
            "seed_knowledge_ids": [str(item) for item in graph.seed_knowledge_ids],
            "expanded_knowledge_ids": [str(item) for item in graph.expanded_knowledge_ids],
            "relation_paths": graph.relation_paths,
        }

    def _related_knowledge_points(
        self,
        evidence: list[EvidenceItem],
    ) -> list[RelatedKnowledgePoint]:
        related: list[RelatedKnowledgePoint] = []
        seen: set[UUID] = set()
        for item in evidence:
            if item.knowledge_id is None or item.knowledge_id in seen:
                continue
            seen.add(item.knowledge_id)
            related.append(
                RelatedKnowledgePoint(
                    knowledge_id=str(item.knowledge_id),
                    name=item.title,
                )
            )
        return related[:5]

    def _follow_up_questions(
        self,
        related: list[RelatedKnowledgePoint],
    ) -> list[str]:
        if not related:
            return []
        name = related[0].name
        return [f"{name}最容易和哪些概念混淆？", f"能用一个例题巩固{name}吗？"]

    def _save_candidate(self, question: str, answer: str) -> str:
        return (
            "## AI Tutor 问答沉淀\n\n"
            f"### 问题\n{question}\n\n"
            f"### 回答摘要\n{answer[:800]}"
        )
