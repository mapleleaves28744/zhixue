from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import select

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.registry import AgentRegistry
from app.llm import ChatMessage, get_llm_provider
from app.models.knowledge import KnowledgePoint
from app.models.wiki import WikiPage
from app.rag.retriever import VectorRetriever
from app.schemas.resource import RESOURCE_TYPE_ALIASES, VALID_RESOURCE_TYPES
from app.services.memory_service import MemoryService
from app.services.prompt_service import PromptService
from app.services.profile_service import ProfileService


RESOURCE_TYPE_LABELS = {
    "explanation": "讲解",
    "summary": "总结",
    "example": "例题",
    "flashcard": "复习卡",
    "review": "错题解析",
}


@AgentRegistry.register
class ResourceAgent(BaseAgent):
    name = "ResourceAgent"
    description = "基于知识点生成个性化学习资源"

    async def run(self, context: AgentContext) -> AgentResult:
        resource_type = self._normalize_resource_type(
            str(context.params.get("resource_type") or "explanation")
        )
        if resource_type not in VALID_RESOURCE_TYPES:
            return self.error_result(message=f"不支持的资源类型: {resource_type}")

        knowledge_id = self._uuid(context.params.get("knowledge_id"))
        wiki_page_id = self._uuid(context.params.get("wiki_page_id"))

        knowledge = await self._get_knowledge(context.course_id, knowledge_id)
        wiki_page = await self._get_wiki_page(context.user_id, context.course_id, wiki_page_id)

        knowledge_name = (
            str(context.params.get("knowledge_name") or "").strip()
            or (knowledge.name if knowledge else "")
            or (wiki_page.title if wiki_page else "")
            or "数据结构"
        )
        requirement = str(context.params.get("requirement") or "").strip()

        retriever = VectorRetriever(self.db)
        results = []
        try:
            results = await retriever.search(
                course_id=context.course_id,
                query=knowledge_name,
                top_k=3,
                knowledge_id=knowledge_id,
            )
            rag_context = "\n\n".join(r.content for r in results) if results else "无参考资料"
        except Exception:
            rag_context = "检索失败：该课程可能尚未生成向量切片，资源将仅基于 Wiki、画像与 Mock 知识生成。"

        profile_text = "未启用画像"
        if context.params.get("use_profile", True):
            profile = await ProfileService(self.db).get_profile(context.user_id)
            memories = await MemoryService(self.db).list_memories(
                context.user_id,
                context.course_id,
            )
            profile_text = self._format_profile(profile, memories)

        wiki_context = wiki_page.content[:2500] if wiki_page else "未指定 Wiki 页面"

        prompts = PromptService(self.db)
        rendered = await prompts.render_prompt(
            agent_name="ResourceAgent",
            scene="resource.generate",
            params={
                "knowledge_name": knowledge_name,
                "resource_type": RESOURCE_TYPE_LABELS[resource_type],
                "student_profile": profile_text,
                "requirement": requirement or "无额外要求",
                "wiki_context": wiki_context,
                "context": rag_context[:3000],
            },
        )

        llm = get_llm_provider(
            db=self.db,
            user_id=context.user_id,
            course_id=context.course_id,
            agent_run_id=context.run_id,
            prompt_version_id=self._uuid(rendered.prompt_version_id),
        )
        response = await llm.chat(
            [ChatMessage(role="user", content=rendered.content)],
            temperature=0.7,
            max_tokens=4096,
            user_id=context.user_id,
            course_id=context.course_id,
            agent_run_id=context.run_id,
            prompt_version_id=rendered.prompt_version_id,
        )

        citations = self._build_citations(wiki_page, results)
        title = self._extract_title(
            response.content,
            resource_type=resource_type,
            knowledge_name=knowledge_name,
        )
        personalized_reason = self._build_personalized_reason(
            resource_type=resource_type,
            knowledge_name=knowledge_name,
            profile_text=profile_text,
            requirement=requirement,
        )

        return self.success_result(
            data={
                "title": title,
                "content": response.content,
                "citations": citations,
                "personalized_reason": personalized_reason,
                "resource_type": resource_type,
                "knowledge_name": knowledge_name,
                "model_name": response.model,
                "prompt_version_id": str(rendered.prompt_version_id) if rendered.prompt_version_id else None,
                "agent_run_id": str(context.run_id) if context.run_id else None,
            },
            message="学习资源生成成功",
            evidence=[f"基于 {len(citations)} 条来源生成"] if citations else ["无检索依据，已标注为建议核对"],
        )

    async def _get_knowledge(
        self,
        course_id: UUID,
        knowledge_id: UUID | None,
    ) -> KnowledgePoint | None:
        if knowledge_id is None:
            return None
        result = await self.db.execute(
            select(KnowledgePoint).where(
                KnowledgePoint.id == knowledge_id,
                KnowledgePoint.course_id == course_id,
            )
        )
        return result.scalar_one_or_none()

    async def _get_wiki_page(
        self,
        user_id: UUID,
        course_id: UUID,
        wiki_page_id: UUID | None,
    ) -> WikiPage | None:
        if wiki_page_id is None:
            return None
        result = await self.db.execute(
            select(WikiPage).where(
                WikiPage.id == wiki_page_id,
                WikiPage.owner_id == user_id,
                WikiPage.course_id == course_id,
                WikiPage.status == "active",
            )
        )
        return result.scalar_one_or_none()

    def _normalize_resource_type(self, value: str) -> str:
        cleaned = value.strip()
        return RESOURCE_TYPE_ALIASES.get(cleaned, cleaned.lower())

    def _uuid(self, value: object) -> UUID | None:
        if isinstance(value, UUID):
            return value
        if isinstance(value, str) and value:
            try:
                return UUID(value)
            except ValueError:
                return None
        return None

    def _format_profile(self, profile: object, memories: list[object]) -> str:
        parts: list[str] = []
        summary = getattr(profile, "profile_summary", None)
        if summary:
            parts.append(f"画像摘要：{summary}")
        learning_goal = getattr(profile, "learning_goal", None)
        if learning_goal:
            parts.append(f"学习目标：{learning_goal}")
        weak_points = getattr(profile, "weak_points", None)
        if weak_points:
            parts.append(f"薄弱点：{weak_points}")
        error_patterns = getattr(profile, "error_patterns", None)
        if error_patterns:
            parts.append(f"常见错误：{error_patterns}")
        if memories:
            memory_text = "；".join(getattr(memory, "content", "") for memory in memories[:5] if getattr(memory, "content", ""))
            if memory_text:
                parts.append(f"长期记忆：{memory_text}")
        return "\n".join(parts) if parts else "一般学习状态：需要通过分步骤解释和可验证练习巩固。"

    def _build_citations(
        self,
        wiki_page: WikiPage | None,
        results: list[object],
    ) -> list[dict[str, object]]:
        citations: list[dict[str, object]] = []
        if wiki_page is not None:
            citations.append(
                {
                    "source_type": "wiki",
                    "source_id": str(wiki_page.id),
                    "page_id": str(wiki_page.id),
                    "title": wiki_page.title,
                }
            )
        for result in results:
            citations.append(
                {
                    "source_type": "document",
                    "source_id": str(getattr(result, "material_id")),
                    "chunk_id": str(getattr(result, "chunk_id")),
                    "title": getattr(result, "source_title", None) or "课程资料片段",
                    "page_no": getattr(result, "page_no", None),
                    "score": round(float(getattr(result, "score", 0) or 0), 4),
                    "quote": str(getattr(result, "content", ""))[:180],
                }
            )
        if not citations:
            citations.append(
                {
                    "source_type": "inference",
                    "title": "AI 推断内容，建议核对资料",
                    "quote": "当前课程尚未提供可用 Wiki 或向量检索片段。",
                }
            )
        return citations

    def _extract_title(
        self,
        content: str,
        *,
        resource_type: str,
        knowledge_name: str,
    ) -> str:
        match = re.search(r"^#\s+(.+)$", content.strip(), flags=re.MULTILINE)
        if match:
            return match.group(1).strip()[:255]
        return f"{knowledge_name}{RESOURCE_TYPE_LABELS[resource_type]}"[:255]

    def _build_personalized_reason(
        self,
        *,
        resource_type: str,
        knowledge_name: str,
        profile_text: str,
        requirement: str,
    ) -> str:
        label = RESOURCE_TYPE_LABELS[resource_type]
        if requirement:
            return f"根据你的补充要求“{requirement[:80]}”，本次围绕「{knowledge_name}」生成{label}，并优先采用分步骤、可核对来源的表达。"
        if "薄弱点" in profile_text or "常见错误" in profile_text:
            return f"结合你的画像/记忆中暴露的薄弱点，本次用更细的层次拆解「{knowledge_name}」，帮助你把概念、过程和应用场景连起来。"
        return f"当前缺少充分个性化证据，因此先按数据结构课程的一般学习路径生成「{knowledge_name}」{label}；建议结合引用来源核对。"
