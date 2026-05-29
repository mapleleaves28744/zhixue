from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.registry import AgentRegistry
from app.llm import ChatMessage, get_llm_provider
from app.rag.retriever import VectorRetriever
from app.services.prompt_service import PromptService


@AgentRegistry.register
class RecommendAgent(BaseAgent):
    name = "RecommendAgent"
    description = "基于学生画像推荐学习资源"

    async def run(self, context: AgentContext) -> AgentResult:
        topic = context.params.get("topic", "")
        if not topic:
            return self.error_result(message="缺少 topic 参数")

        retriever = VectorRetriever(self.db)
        try:
            results = await retriever.search(
                course_id=context.course_id,
                query=topic,
                user_id=context.user_id,
                top_k=5,
            )
            ref_context = "\n\n".join(r.content for r in results) if results else "无相关资料"
        except Exception:
            ref_context = "检索失败"

        prompts = PromptService(self.db)
        rendered = await prompts.render_prompt(
            agent_name="RecommendAgent",
            scene="recommend.resources",
            params={
                "topic": topic,
                "student_profile": context.params.get("student_profile", ""),
                "context": ref_context[:3000],
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
            data={"recommendations": response.content, "topic": topic},
            message="资源推荐完成",
            evidence=[f"基于 {len(results)} 个相关资料推荐"] if results else ["无检索依据"],
        )
