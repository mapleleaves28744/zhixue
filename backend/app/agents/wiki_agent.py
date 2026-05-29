from __future__ import annotations

from uuid import UUID

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.registry import AgentRegistry
from app.llm import ChatMessage, get_llm_provider
from app.rag.retriever import VectorRetriever
from app.services.prompt_service import PromptService


@AgentRegistry.register
class WikiAgent(BaseAgent):
    name = "WikiAgent"
    description = "将课程资料转换为 Wiki 页面"

    async def run(self, context: AgentContext) -> AgentResult:
        material_id = context.params.get("material_id")
        if not material_id:
            return self.error_result(message="缺少 material_id 参数")

        retriever = VectorRetriever(self.db)
        try:
            results = await retriever.search(
                course_id=context.course_id,
                query=context.params.get("title", ""),
                user_id=context.user_id,
                top_k=5,
            )
            chunk_text = "\n\n".join(r.content for r in results) if results else "无相关资料"
        except Exception:
            chunk_text = "检索失败，使用原始内容"

        prompts = PromptService(self.db)
        rendered = await prompts.render_prompt(
            agent_name="WikiAgent",
            scene="wiki.generate",
            params={
                "knowledge_name": context.params.get("title", ""),
                "knowledge_description": context.params.get("description", ""),
                "chunk_text": chunk_text[:3000],
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
            max_tokens=4096,
        )

        return self.success_result(
            data={"wiki_content": response.content, "material_id": str(material_id)},
            message="Wiki 生成成功",
            evidence=[f"基于 {len(results)} 个文档片段检索生成"] if results else ["无检索依据"],
        )
