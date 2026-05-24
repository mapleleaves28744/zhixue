from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.registry import AgentRegistry
from app.llm import ChatMessage, get_llm_provider
from app.services.prompt_service import PromptService


@AgentRegistry.register
class QuizAgent(BaseAgent):
    name = "QuizAgent"
    description = "基于知识点生成练习题"

    async def run(self, context: AgentContext) -> AgentResult:
        knowledge_name = context.params.get("knowledge_name", "")
        if not knowledge_name:
            return self.error_result(message="缺少 knowledge_name 参数")

        prompts = PromptService(self.db)
        rendered = await prompts.render_prompt(
            agent_name="QuizAgent",
            scene="quiz.generate",
            params={
                "knowledge_name": knowledge_name,
                "knowledge_description": context.params.get("knowledge_description", ""),
                "difficulty": context.params.get("difficulty", "medium"),
                "count": context.params.get("count", 5),
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
            temperature=0.8,
            max_tokens=4096,
        )

        return self.success_result(
            data={"quiz_content": response.content, "knowledge_name": knowledge_name},
            message="练习题生成成功",
            evidence=[f"基于知识点「{knowledge_name}」生成"],
        )
