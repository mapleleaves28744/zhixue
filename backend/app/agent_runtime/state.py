from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


class PlannedToolCall(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentDecision(BaseModel):
    status: Literal["continue", "complete", "replan", "waiting_confirmation", "failed"]
    summary: str = Field(min_length=1, max_length=1000)
    plan: list[str] = Field(default_factory=list, max_length=30)
    tool_calls: list[PlannedToolCall] = Field(default_factory=list, max_length=10)
    final_answer: str = ""
    risk_level: Literal["low", "medium", "high"] = "low"
    reasoning_content: str | None = None


class AgentState(TypedDict, total=False):
    conversation_id: str
    task_id: str
    thread_id: str
    user_id: str
    course_id: str
    goal: str
    messages: list[dict[str, Any]]
    context: dict[str, Any]
    current_plan: list[str]
    pending_tool_calls: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    observations: list[dict[str, Any]]
    artifacts: list[dict[str, Any]]
    citations: list[Any]
    iteration_count: int
    tool_call_count: int
    replan_count: int
    max_iterations: int
    max_tool_calls: int
    max_replans: int
    risk_level: str
    status: str
    decision_summary: str
    final_answer: str
    error_message: str
    protocol_reasoning_content: str
    last_tool_result: dict[str, Any]
    review_result: dict[str, Any]
    approved_tool_call_ids: list[str]
    tool_hints: list[str]
    skip_tools: list[str]
