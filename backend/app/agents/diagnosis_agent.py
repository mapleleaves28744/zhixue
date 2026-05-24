from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.registry import AgentRegistry
from app.llm import ChatMessage, get_llm_provider
from app.services.prompt_service import PromptService


@AgentRegistry.register
class DiagnosisAgent(BaseAgent):
    name = "DiagnosisAgent"
    description = "分析答题记录，诊断学习薄弱点"

    async def run(self, context: AgentContext) -> AgentResult:
        diagnosis_context = context.params.get("diagnosis_context", "")
        if not diagnosis_context:
            return self.error_result(message="缺少 diagnosis_context 参数")

        prompts = PromptService(self.db)
        rendered = await prompts.render_prompt(
            agent_name="DiagnosisAgent",
            scene="diagnosis.generate",
            params={"diagnosis_context": diagnosis_context[:3000]},
        )

        llm = get_llm_provider(
            db=self.db,
            user_id=context.user_id,
            course_id=context.course_id,
            agent_run_id=context.run_id,
        )
        response = await llm.chat(
            [ChatMessage(role="user", content=rendered.content)],
            temperature=0.5,
            max_tokens=2048,
        )

        return self.success_result(
            data={"diagnosis_result": response.content},
            message="学习诊断完成",
        )
