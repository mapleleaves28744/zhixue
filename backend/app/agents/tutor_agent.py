from __future__ import annotations

from typing import Any
from uuid import UUID

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.registry import AgentRegistry
from app.llm import ChatMessage, get_llm_provider
from app.models.wiki import WikiPage
from app.rag.retriever import VectorRetriever
from app.repositories.wiki_repository import WikiRepository
from app.services.memory_service import MemoryService
from app.services.prompt_service import PromptService
from app.services.profile_service import ProfileService


@AgentRegistry.register
class TutorAgent(BaseAgent):
    name = "TutorAgent"
    description = "基于 RAG、Wiki、画像和记忆的课程问答"

    async def run(self, context: AgentContext) -> AgentResult:
        question = context.params.get("question", "")
        if not question:
            return self.error_result(message="缺少 question 参数")

        use_rag = bool(context.params.get("use_rag", True))
        use_wiki = bool(context.params.get("use_wiki", True))
        use_profile = bool(context.params.get("use_profile", True))
        knowledge_id = self._optional_uuid(context.params.get("knowledge_id"))
        wiki_page_id = self._optional_uuid(context.params.get("wiki_page_id"))

        retriever = VectorRetriever(self.db)
        results = []
        retrieved_context = "未检索到相关资料"
        if use_rag:
            try:
                results = await retriever.search(
                    course_id=context.course_id,
                    query=question,
                    top_k=context.params.get("top_k", 5),
                    knowledge_id=knowledge_id,
                )
                retrieved_context = "\n\n".join(r.content for r in results) if results else "未检索到相关资料"
            except Exception:
                retrieved_context = "未检索到相关资料"

        wiki_pages = await self._load_wiki_pages(
            user_id=context.user_id,
            course_id=context.course_id,
            wiki_page_id=wiki_page_id,
            question=question,
            enabled=use_wiki,
        )
        wiki_context = self._format_wiki_context(wiki_pages)
        student_profile = await self._load_profile(context.user_id, use_profile)
        memory_context = await self._load_memory(context.user_id, context.course_id, use_profile)

        citations = self._build_citations(results, wiki_pages)
        if not citations:
            citations.append(
                {
                    "source_type": "inference",
                    "title": "AI 推断内容，建议核对课程资料",
                    "source_id": None,
                    "quote": "当前课程资料库和 Wiki 未命中明确来源。",
                }
            )
        related_knowledge_points = self._related_knowledge_points(question, wiki_pages)
        follow_up_questions = self._follow_up_questions(related_knowledge_points)

        prompts = PromptService(self.db)
        rendered = await prompts.render_prompt(
            agent_name="TutorAgent",
            scene="tutor.qa",
            params={
                "question": question,
                "retrieved_context": retrieved_context[:3000],
                "wiki_context": wiki_context[:3000],
                "student_profile": student_profile[:1200],
                "memory_context": memory_context[:1200],
            },
        )

        llm = get_llm_provider(
            db=self.db,
            user_id=context.user_id,
            course_id=context.course_id,
            agent_run_id=context.run_id,
        )
        response = await llm.chat(
            [ChatMessage(role="user", content=rendered.content)],
            temperature=0.7,
            max_tokens=2048,
            prompt_version_id=rendered.prompt_version_id,
        )

        answer = response.content.strip()
        if citations and citations[0]["source_type"] == "inference" and "AI 推断内容" not in answer:
            answer = f"{answer}\n\n依据说明：AI 推断内容，建议核对课程资料。"

        return self.success_result(
            data={
                "answer": answer,
                "model": response.model,
                "citations": citations,
                "related_knowledge_points": related_knowledge_points,
                "follow_up_questions": follow_up_questions,
                "save_to_wiki_candidate": self._save_candidate(question, answer),
                "agent_run_id": str(context.run_id) if context.run_id else None,
                "memory_update_suggestion": {
                    "should_reflect": True,
                    "reason": "本次问答可作为学生关注知识点和解释偏好的证据。",
                },
            },
            message="问答完成",
            evidence=[
                f"基于 {len(results)} 个文档片段检索",
                f"关联 {len(wiki_pages)} 个 Wiki 页面",
            ],
        )

    async def _load_wiki_pages(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        wiki_page_id: UUID | None,
        question: str,
        enabled: bool,
    ) -> list[WikiPage]:
        if not enabled:
            return []
        repo = WikiRepository(self.db)
        if wiki_page_id is not None:
            page = await repo.get_by_id_simple(wiki_page_id)
            if page and page.owner_id == user_id and page.course_id == course_id and page.status == "active":
                return [page]
            return []

        pages, _ = await repo.list_by_owner(user_id, course_id, page_size=20)
        scored: list[tuple[int, WikiPage]] = []
        question_lower = question.lower()
        for page in pages:
            haystack = f"{page.title}\n{page.summary or ''}\n{page.content[:800]}".lower()
            score = 0
            for token in self._question_tokens(question_lower):
                if token and token in haystack:
                    score += 1
            if score > 0:
                scored.append((score, page))
        if scored:
            return [page for _, page in sorted(scored, key=lambda item: item[0], reverse=True)[:3]]
        return pages[:3]

    async def _load_profile(self, user_id: UUID, enabled: bool) -> str:
        if not enabled:
            return "未启用学生画像"
        try:
            summary = await ProfileService(self.db).get_summary(user_id)
            return (
                f"画像摘要：{summary.profile_summary or '暂无'}；"
                f"掌握快照：{summary.mastery_snapshot}；"
                f"薄弱点：{summary.weak_points}"
            )
        except Exception:
            return "学生画像暂不可用"

    async def _load_memory(self, user_id: UUID, course_id: UUID, enabled: bool) -> str:
        if not enabled:
            return "未启用长期记忆"
        try:
            memories = await MemoryService(self.db).list_memories(user_id, course_id)
            if not memories:
                return "暂无长期学习记忆"
            return "\n".join(
                f"- {item.memory_type}: {item.content}"
                for item in memories[:5]
            )
        except Exception:
            return "长期记忆暂不可用"

    def _format_wiki_context(self, pages: list[WikiPage]) -> str:
        if not pages:
            return "未检索到相关 Wiki 页面"
        return "\n\n".join(
            f"### {page.title}\n摘要：{page.summary or '暂无摘要'}\n内容片段：{page.content[:900]}"
            for page in pages
        )

    def _build_citations(self, results: list[Any], wiki_pages: list[WikiPage]) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        for result in results[:5]:
            citations.append(
                {
                    "source_type": "document",
                    "title": result.source_title or "课程资料片段",
                    "source_id": str(result.material_id),
                    "chunk_id": str(result.chunk_id),
                    "page_no": result.page_no,
                    "score": round(result.score, 4),
                    "quote": result.content[:160],
                }
            )
        for page in wiki_pages[:3]:
            citations.append(
                {
                    "source_type": "wiki",
                    "title": page.title,
                    "source_id": str(page.id),
                    "page_id": str(page.id),
                    "quote": (page.summary or page.content[:160] or "Wiki 页面"),
                }
            )
        return citations

    def _related_knowledge_points(
        self,
        question: str,
        wiki_pages: list[WikiPage],
    ) -> list[dict[str, str | None]]:
        related = [{"knowledge_id": str(page.id), "name": page.title} for page in wiki_pages[:3]]
        keyword_map = {
            "递归": "递归调用栈",
            "栈": "栈",
            "队列": "队列",
            "二叉树": "二叉树",
            "树": "树结构",
            "图": "图结构",
            "排序": "排序算法",
            "查找": "查找算法",
            "哈希": "哈希表",
        }
        for key, name in keyword_map.items():
            if key in question and all(item["name"] != name for item in related):
                related.append({"knowledge_id": None, "name": name})
        if not related:
            related.append({"knowledge_id": None, "name": "数据结构基础"})
        return related[:5]

    def _follow_up_questions(self, related: list[dict[str, str | None]]) -> list[str]:
        names = [item["name"] for item in related if item.get("name")]
        first = names[0] if names else "这个知识点"
        return [
            f"{first}最容易和哪些概念混淆？",
            f"能不能用一个小例题巩固{first}？",
        ]

    def _save_candidate(self, question: str, answer: str) -> str:
        return (
            "## AI Tutor 问答沉淀\n\n"
            f"### 问题\n{question}\n\n"
            f"### 回答摘要\n{answer[:800]}"
        )

    def _question_tokens(self, question: str) -> list[str]:
        separators = " ，。！？；：,.!?;:\n\t"
        tokens = [question]
        current = ""
        for char in question:
            if char in separators:
                if current:
                    tokens.append(current)
                    current = ""
            else:
                current += char
        if current:
            tokens.append(current)
        return [token.strip() for token in tokens if len(token.strip()) >= 2]

    def _optional_uuid(self, value: object) -> UUID | None:
        if isinstance(value, UUID):
            return value
        if isinstance(value, str) and value:
            try:
                return UUID(value)
            except ValueError:
                return None
        return None
