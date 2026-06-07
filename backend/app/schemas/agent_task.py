from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


TASK_STATUSES = {
    "draft",
    "planned",
    "queued",
    "waiting_confirmation",
    "running",
    "succeeded",
    "failed",
    "cancelled",
}
STEP_STATUSES = {"pending", "running", "succeeded", "failed", "skipped"}

ALLOWED_AGENT_ACTIONS = {
    ("PlannerAgent", "generate_learning_path"),
    ("ResourceAgent", "generate_explanation"),
    ("ResourceAgent", "generate_html_classroom_draft"),
    ("QuizAgent", "generate_quiz"),
    ("ProfileAgent", "rebuild_profile_draft"),
    ("RecommendAgent", "generate_recommendations"),
    ("ReviewAgent", "review_artifacts"),
}


class AgentTaskPlanStep(BaseModel):
    step: int = Field(ge=1)
    agent: str = Field(min_length=1, max_length=128)
    action: str = Field(min_length=1, max_length=128)
    skill: str | None = Field(default=None, max_length=128)
    input: dict[str, Any] = Field(default_factory=dict)
    expected_output: str = Field(min_length=1, max_length=255)
    writes: list[str] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"] = "low"
    requires_confirmation: bool = False

    @model_validator(mode="after")
    def validate_whitelist(self) -> AgentTaskPlanStep:
        if (self.agent, self.action) not in ALLOWED_AGENT_ACTIONS:
            raise ValueError(f"不允许的 Agent/action: {self.agent}/{self.action}")
        return self


class AgentTaskPlan(BaseModel):
    plan_schema_version: str = "1.0"
    goal: str = Field(min_length=1, max_length=1000)
    risk_level: Literal["low", "medium", "high"] = "low"
    requires_confirmation: bool = False
    target_knowledge: list[str] = Field(default_factory=list)
    requested_artifacts: list[str] = Field(default_factory=list)
    steps: list[AgentTaskPlanStep] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_step_order(self) -> AgentTaskPlan:
        expected = list(range(1, len(self.steps) + 1))
        if [item.step for item in self.steps] != expected:
            raise ValueError("计划步骤必须从 1 开始连续编号")
        if any(step.requires_confirmation for step in self.steps):
            self.requires_confirmation = True
        if any(step.risk_level == "high" for step in self.steps):
            self.risk_level = "high"
        elif self.risk_level == "low" and any(step.risk_level == "medium" for step in self.steps):
            self.risk_level = "medium"
        return self


class AgentTaskCreateRequest(BaseModel):
    course_id: UUID
    user_input: str = Field(min_length=2, max_length=2000)


class AgentTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    course_id: UUID
    conversation_id: UUID | None = None
    thread_id: str | None = None
    task_goal: str
    task_type: str
    status: str
    plan_schema_version: str
    graph_version: str = "langgraph-1.0"
    runtime_mode: str = "langgraph"
    plan_json: dict[str, Any] = Field(default_factory=dict)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    intent_payload: dict[str, Any] = Field(default_factory=dict)
    risk_level: str
    requires_confirmation: bool
    confirmed_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    cancelled_at: datetime | None = None
    error_message: str | None = None
    iteration_count: int = 0
    tool_call_count: int = 0
    replan_count: int = 0
    checkpoint_id: str | None = None
    last_event_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AgentTaskStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    step_index: int
    agent_name: str
    skill_name: str | None = None
    action: str
    expected_output: str | None = None
    status: str
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_payload: dict[str, Any] = Field(default_factory=dict)
    evidence: list[Any] = Field(default_factory=list)
    artifact_refs: list[Any] = Field(default_factory=list)
    related_agent_run_id: UUID | None = None
    tool_call_id: str | None = None
    parent_step_id: UUID | None = None
    iteration_no: int = 0
    node_name: str | None = None
    decision_summary: str | None = None
    retry_count: int
    duration_ms: int | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


def build_task_plan(intent: dict[str, Any]) -> AgentTaskPlan:
    task_type = str(intent.get("task_type") or "personalized_learning_package")
    common = {
        "goal": str(intent.get("goal") or "完成个性化学习任务"),
        "risk_level": intent.get("risk_level") or "low",
        "requires_confirmation": bool(intent.get("requires_confirmation")),
        "target_knowledge": list(intent.get("target_knowledge") or []),
        "requested_artifacts": list(intent.get("requested_artifacts") or []),
    }
    if task_type == "profile_interview_plan":
        steps = [
            _step(1, "ProfileAgent", "rebuild_profile_draft", "profile_update", ["student_profiles"]),
            _step(2, "RecommendAgent", "generate_recommendations", "recommendations", ["recommendations"]),
            _step(3, "ReviewAgent", "review_artifacts", "review_result"),
        ]
    elif task_type == "html_classroom_request":
        steps = [
            _step(
                1,
                "ResourceAgent",
                "generate_html_classroom_draft",
                "html_classroom",
                ["generated_resources"],
                skill="html_classroom",
            ),
            _step(2, "ReviewAgent", "review_artifacts", "review_result"),
        ]
    else:
        steps = [
            _step(1, "PlannerAgent", "generate_learning_path", "learning_path", ["learning_paths"]),
            _step(2, "ResourceAgent", "generate_explanation", "resource", ["generated_resources"]),
            _step(3, "QuizAgent", "generate_quiz", "quiz", ["quizzes", "questions"]),
            _step(4, "ReviewAgent", "review_artifacts", "review_result"),
        ]
    if common["requires_confirmation"]:
        for step in steps:
            step.requires_confirmation = True
            step.risk_level = common["risk_level"]
    return AgentTaskPlan(**common, steps=steps)


def _step(
    index: int,
    agent: str,
    action: str,
    expected_output: str,
    writes: list[str] | None = None,
    *,
    skill: str | None = None,
) -> AgentTaskPlanStep:
    return AgentTaskPlanStep(
        step=index,
        agent=agent,
        action=action,
        skill=skill,
        expected_output=expected_output,
        writes=writes or [],
    )
