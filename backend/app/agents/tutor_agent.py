from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.registry import AgentRegistry
from app.llm import ChatMessage, get_llm_provider
from app.rag.retriever import VectorRetriever
from app.services.prompt_service import PromptService


@AgentRegistry.register
class TutorAgent(BaseAgent):
    name = "TutorAgent"
    description = "基于 RAG 的课程问答"

    async def run(self, context: AgentContext) -> AgentResult:
        question = context.params.get("question", "")
        if not question:
            return self.error_result(message="缺少 question 参数")

        retriever = VectorRetriever(self.db)
        try:
            results = await retriever.search(
                course_id=context.course_id,
                query=question,
                top_k=context.params.get("top_k", 5),
            )
            retrieved_context = "\n\n".join(r.content for r in results) if results else "未检索到相关资料"
        except Exception:
            retrieved_context = "未检索到相关资料"
            results = []

        prompts = PromptService(self.db)
        rendered = await prompts.render_prompt(
            agent_name="TutorAgent",
            scene="tutor.qa",
            params={
                "question": question,
                "retrieved_context": retrieved_context[:3000],
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
        )

        return self.success_result(
            data={
                "answer": response.content,
                "model": response.model,
                "sources": [
                    {
                        "chunk_id": str(r.chunk_id),
                        "source_title": r.source_title,
                        "score": round(r.score, 4),
                    }
                    for r in results
                ],
            },
            message="问答完成",
            evidence=[f"基于 {len(results)} 个文档片段检索"] if results else ["无检索依据"],
        )
