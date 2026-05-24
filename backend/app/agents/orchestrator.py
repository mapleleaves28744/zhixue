from __future__ import annotations

import logging
from time import perf_counter

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.registry import AgentRegistry
from app.services.agent_log_service import AgentLogService

logger = logging.getLogger(__name__)

TASK_AGENT_PLAN: dict[str, list[str]] = {
    "document_to_wiki": ["WikiAgent"],
    "course_qa": ["TutorAgent"],
    "extract_knowledge": ["KnowledgeAgent"],
    "generate_quiz": ["QuizAgent"],
    "generate_resource": ["ResourceAgent"],
    "diagnose_student": ["DiagnosisAgent"],
    "recommend_resources": ["RecommendAgent"],
    "evolve_strategy": ["EvolutionAgent"],
    "review_content": ["ReviewAgent"],
    "plan_learning": ["PlannerAgent"],
    "update_profile": ["ProfileAgent"],
}


class OrchestratorAgent(BaseAgent):
    name = "OrchestratorAgent"
    description = "根据 task_type 路由到对应 Agent 链执行"

    async def run(self, context: AgentContext) -> AgentResult:
        plan = TASK_AGENT_PLAN.get(context.task_type)
        if not plan:
            return self.error_result(message=f"未知任务类型: {context.task_type}")

        log_service = AgentLogService(self.db)
        result: AgentResult | None = None

        for agent_name in plan:
            agent_cls = AgentRegistry.get(agent_name)
            if agent_cls is None:
                return self.error_result(message=f"Agent 未注册: {agent_name}")

            run_log = await log_service.start_run(
                task_type=context.task_type,
                agent_name=agent_name,
                input_payload={"params": context.params, "metadata": context.metadata},
                user_id=context.user_id,
                course_id=context.course_id,
            )
            context.run_id = run_log.id
            started = perf_counter()

            try:
                agent = agent_cls(db=self.db)
                result = await agent.run(context)
            except Exception as exc:
                duration_ms = int((perf_counter() - started) * 1000)
                await log_service.finish_run(
                    run_id=run_log.id,
                    output_payload={},
                    status="failed",
                    duration_ms=duration_ms,
                    error_message=str(exc),
                )
                logger.exception("Agent %s 执行异常", agent_name)
                return self.error_result(message=f"Agent {agent_name} 执行异常: {exc}")

            duration_ms = int((perf_counter() - started) * 1000)
            await log_service.finish_run(
                run_id=run_log.id,
                output_payload=result.data,
                status="success" if result.success else "failed",
                duration_ms=duration_ms,
                error_message=result.message if not result.success else None,
            )

            if not result.success:
                return result
            context.metadata.update(result.data)

        return result  # type: ignore[return-value]
