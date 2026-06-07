from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Awaitable, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_task import AgentTask, AgentTaskStep
from app.models.user import User
from app.repositories.agent_task_repository import AgentTaskRepository


@dataclass
class StepExecutionResult:
    output: dict[str, Any] = field(default_factory=dict)
    evidence: list[Any] = field(default_factory=list)
    artifact_refs: list[Any] = field(default_factory=list)
    related_agent_run_id: UUID | None = None


StepExecutor = Callable[
    [AgentTaskStep, AgentTask, User, list[Any]],
    Awaitable[StepExecutionResult],
]


class LearningTaskGraph:
    def __init__(
        self,
        db: AsyncSession,
        *,
        repository: AgentTaskRepository | None = None,
        step_executor: StepExecutor | None = None,
    ) -> None:
        self.db = db
        self.tasks = repository or AgentTaskRepository(db)
        self.step_executor = step_executor or self._execute_step

    async def run(self, *, task: AgentTask, current_user: User) -> AgentTask:
        artifact_refs = list(task.plan_json.get("artifact_refs") or [])
        await self.tasks.update_task(
            task,
            status="running",
            started_at=datetime.now(UTC),
            finished_at=None,
            error_message=None,
        )
        await self.db.commit()

        for step in await self.tasks.list_steps(task.id):
            if await self._is_cancelled(task):
                await self.tasks.skip_pending_steps(task.id, "任务已取消")
                await self.tasks.update_task(
                    task,
                    plan_json={**task.plan_json, "artifact_refs": artifact_refs},
                )
                await self.db.commit()
                return task
            started = perf_counter()
            await self.tasks.update_step(
                step,
                status="running",
                started_at=datetime.now(UTC),
                finished_at=None,
                error_message=None,
            )
            await self.db.commit()
            try:
                result = await self.step_executor(step, task, current_user, artifact_refs)
            except Exception as exc:
                error_message = str(exc)[:2000]
                await self.tasks.update_step(
                    step,
                    status="failed",
                    error_message=error_message,
                    duration_ms=int((perf_counter() - started) * 1000),
                    finished_at=datetime.now(UTC),
                )
                await self.tasks.skip_pending_steps(task.id, "前序步骤失败，未执行")
                await self.tasks.update_task(
                    task,
                    status="failed",
                    error_message=error_message,
                    finished_at=datetime.now(UTC),
                    plan_json={**task.plan_json, "artifact_refs": artifact_refs},
                )
                await self.db.commit()
                return task

            artifact_refs.extend(result.artifact_refs)
            await self.tasks.update_step(
                step,
                status="succeeded",
                output_payload=result.output,
                evidence=result.evidence,
                artifact_refs=result.artifact_refs,
                related_agent_run_id=result.related_agent_run_id,
                duration_ms=int((perf_counter() - started) * 1000),
                finished_at=datetime.now(UTC),
            )
            await self.db.commit()

        await self.tasks.update_task(
            task,
            status="succeeded",
            plan_json={**task.plan_json, "artifact_refs": artifact_refs},
            finished_at=datetime.now(UTC),
        )
        await self.db.commit()
        return task

    async def _is_cancelled(self, task: AgentTask) -> bool:
        if task.status == "cancelled":
            return True
        refresh = getattr(self.db, "refresh", None)
        if callable(refresh):
            await refresh(task)
        return task.status == "cancelled"

    async def _execute_step(
        self,
        step: AgentTaskStep,
        task: AgentTask,
        current_user: User,
        artifact_refs: list[Any],
    ) -> StepExecutionResult:
        key = (step.agent_name, step.action)
        topic = "、".join(task.intent_payload.get("target_knowledge") or []) or task.task_goal

        if key == ("PlannerAgent", "generate_learning_path"):
            from app.schemas.learning_path import LearningPathGenerateRequest
            from app.services.learning_path_service import LearningPathService

            result = await LearningPathService(self.db).generate(
                payload=LearningPathGenerateRequest(course_id=task.course_id, goal=task.task_goal),
                current_user=current_user,
            )
            return StepExecutionResult(
                output={"id": str(result.id), "title": result.title, "items": len(result.items)},
                evidence=[result.reason or "基于课程知识点和目标生成"],
                artifact_refs=[{"type": "learning_path", "id": str(result.id), "title": result.title}],
            )

        if key in {
            ("ResourceAgent", "generate_explanation"),
            ("ResourceAgent", "generate_html_classroom_draft"),
        }:
            from app.schemas.resource import ResourceGenerateRequest
            from app.services.resource_service import ResourceService

            html_mode = step.action == "generate_html_classroom_draft"
            requirement = (
                f"围绕{topic}生成可在浏览器展示的 HTML 课堂讲解草稿，包含讲解顺序、示例和互动提示。"
                if html_mode
                else f"围绕{topic}生成分步骤讲解资料，并引用课程资料。"
            )
            result = await ResourceService(self.db).generate_resource(
                payload=ResourceGenerateRequest(
                    course_id=task.course_id,
                    resource_type="explanation",
                    requirement=requirement,
                    use_profile=True,
                ),
                current_user=current_user,
            )
            artifact_type = "html_classroom" if html_mode else "resource"
            return StepExecutionResult(
                output={
                    "resource_id": str(result.resource_id),
                    "title": result.title,
                    "review_result": result.review_result,
                },
                evidence=result.citations,
                artifact_refs=[
                    {"type": artifact_type, "id": str(result.resource_id), "title": result.title}
                ],
                related_agent_run_id=result.agent_run_id,
            )

        if key == ("QuizAgent", "generate_quiz"):
            from app.schemas.quiz import QuizGenerateRequest
            from app.services.quiz_service import QuizService

            result = await QuizService(self.db).generate_quiz(
                payload=QuizGenerateRequest(
                    course_id=task.course_id,
                    topic=topic,
                    count=3,
                    question_types=["single_choice", "short_answer"],
                ),
                current_user=current_user,
            )
            return StepExecutionResult(
                output={"quiz_id": str(result.quiz_id), "title": result.title, "questions": len(result.questions)},
                evidence=[f"生成 {len(result.questions)} 道结构化练习"],
                artifact_refs=[{"type": "quiz", "id": str(result.quiz_id), "title": result.title}],
                related_agent_run_id=result.agent_run_id,
            )

        if key == ("ProfileAgent", "rebuild_profile_draft"):
            from app.services.profile_service import ProfileService

            result = await ProfileService(self.db).rebuild(current_user.id)
            return StepExecutionResult(
                output={"profile_id": str(result.id), "version_no": result.version_no},
                evidence=["基于当前用户学习记录重建"],
                artifact_refs=[{"type": "profile_update", "id": str(result.id)}],
            )

        if key == ("RecommendAgent", "generate_recommendations"):
            from app.services.recommendation_service import RecommendationService

            result = await RecommendationService(self.db).refresh_recommendations(
                current_user=current_user,
                course_id=task.course_id,
            )
            return StepExecutionResult(
                output=result,
                evidence=["基于画像、诊断和学习路径刷新"],
                artifact_refs=[{"type": "recommendations", "count": result["refreshed_count"]}],
            )

        if key == ("ReviewAgent", "review_artifacts"):
            from app.services.agent_service import AgentService

            result = await AgentService(self.db).run_task(
                task_type="review_content",
                user_id=current_user.id,
                course_id=task.course_id,
                params={"content": json.dumps(artifact_refs, ensure_ascii=False)[:4000]},
            )
            if not result.success:
                raise RuntimeError(result.message)
            return StepExecutionResult(
                output=result.data,
                evidence=result.evidence or ["ReviewAgent 已审查产物清单"],
                artifact_refs=[{"type": "review_result", "risk_level": result.data.get("risk_level", "medium")}],
            )

        raise ValueError(f"不允许执行的 Agent/action: {step.agent_name}/{step.action}")
