"""Versioned, bounded description of the user's requested Agent deliverables."""

from __future__ import annotations

import re
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.agent_runtime import supervisor_intents


NON_ARTIFACT_TOOLS = frozenset({"transcribe_audio", "search_course_knowledge", "search_web",
                               "search_conversation_history", "answer_course_question", "review_artifacts",
                               "reflect_learning_memory"})


def valid_non_artifact_output(name: str, output: Any) -> bool:
    if not isinstance(output, dict):
        return False
    if name == "transcribe_audio":
        return bool(str(output.get("text") or "").strip())
    if name in {"search_course_knowledge", "search_web", "search_conversation_history"}:
        return isinstance(output.get("items"), list)
    if name == "answer_course_question":
        return bool(str(output.get("answer") or "").strip())
    if name == "review_artifacts":
        return isinstance(output.get("pass"), bool) and isinstance(output.get("issues"), list)
    if name == "reflect_learning_memory":
        return isinstance(output.get("memories"), list)
    return False


class IntentSubtask(BaseModel):
    id: str = Field(min_length=1, max_length=32)
    segment: str = Field(min_length=1, max_length=500)
    topic: str = Field(min_length=1, max_length=240)
    tools: list[str] = Field(min_length=1, max_length=10)
    source_message_id: UUID
    acceptance: dict[str, str] = Field(default_factory=dict)


class IntentFrame(BaseModel):
    schema_version: Literal["v1"] = "v1"
    request_message_id: UUID
    original_request_message_id: UUID | None = None
    revision: int = Field(default=1, ge=1)
    mode: Literal["answer", "execute", "clarify"]
    parser: Literal["rule_candidates_v1", "semantic_v1"] = "rule_candidates_v1"
    tasks: list[IntentSubtask] = Field(default_factory=list, max_length=8)
    exclusions: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    unresolved_slots: list[str] = Field(default_factory=list)
    clarification_question: str | None = None
    resolved_goal: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def unique_subtasks(self) -> "IntentFrame":
        if len({task.id for task in self.tasks}) != len(self.tasks):
            raise ValueError("subtask IDs must be unique")
        return self


def build_intent_frame(
    *, goal: str, request_message_id: UUID, skip_tools: list[str] | None = None,
    fallback_topic: str | None = None,
    original_request_message_id: UUID | None = None,
    revision: int = 1,
) -> IntentFrame:
    candidates = supervisor_intents.parse_goal_intents(goal)
    if len(candidates) > 8:
        raise ValueError("单次请求最多支持 8 个交付子任务，请分批提交")
    excluded = set(skip_tools or [])
    if not fallback_topic and any(
        _vague_topic(item.topic) and any(name not in excluded for name in item.tools)
        for item in candidates
    ):
        return IntentFrame(
            request_message_id=request_message_id,
            original_request_message_id=original_request_message_id,
            revision=revision, mode="clarify",
            exclusions=list(skip_tools or []),
            unresolved_slots=["topic"],
            clarification_question="你想围绕哪个知识点继续？请直接回复知识点名称。",
            uncertainty=["无法从当前会话确定唯一知识点"],
        )
    tasks = [
        IntentSubtask(
            id=f"s{index}", segment=item.segment[:500],
            topic=(fallback_topic if fallback_topic and _vague_topic(item.topic) else item.topic)[:240],
            tools=[name for name in item.tools if name not in excluded],
            source_message_id=original_request_message_id or request_message_id,
            acceptance={
                "kind": "tool_result" if all(name in NON_ARTIFACT_TOOLS for name in item.tools)
                else "tool_result_and_artifact",
                "topic": (fallback_topic if fallback_topic and _vague_topic(item.topic) else item.topic)[:240],
            },
        )
        for index, item in enumerate(candidates, start=1)
        if any(name not in excluded for name in item.tools)
    ]
    return IntentFrame(
        request_message_id=request_message_id,
        original_request_message_id=original_request_message_id,
        revision=revision,
        mode="execute" if tasks else "answer",
        tasks=tasks,
        exclusions=list(skip_tools or []),
        uncertainty=["规则候选需由执行器核验"] if tasks else [],
    )


def _vague_topic(topic: str) -> bool:
    value = topic.strip()
    return bool(re.search(r"道(?:题|练习)|同类题|^(?:这个|那个|上面|刚才|它|来几个|来一组)", value))


def follow_up_topic(*, goal: str, previous_question: str | None) -> str | None:
    if not previous_question or not re.match(r"^(?:再|继续|刚才|上面|这个|那个|同类)", goal.strip()):
        return None
    if any(marker in previous_question for marker in ("各", "分别")) and any(
        connector in previous_question for connector in ("和", "与", "、")
    ):
        return None
    previous = supervisor_intents.parse_goal_intents(previous_question)
    if len(previous) != 1:
        return None
    topic = previous[0].topic.strip()
    return topic if topic and not _vague_topic(topic) else None


def looks_like_topic_answer(text: str) -> bool:
    value = text.strip()
    return bool(value) and len(value) <= 24 and not re.search(
        r"[？?。！!，,；;]|什么|怎么|为什么|解释|讲解|生成|制作|推荐|搜索|帮我|请问|取消|算了",
        value,
    )


def subtask_progress(frame: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    """Project actual tool results onto distinct requested topics without tool-name deduping."""
    successful = {
        str(item.get("tool_call_id")): item
        for item in result.get("observations") or []
        if item.get("success") is True and item.get("tool_call_id")
    }
    failed = {
        str(item.get("tool_call_id")): item
        for item in result.get("observations") or []
        if item.get("success") is False and item.get("tool_call_id")
    }
    calls = list(result.get("tool_calls") or [])
    tasks = list(frame.get("tasks") or [])
    repeated = {
        name for task in tasks for name in task.get("tools") or []
        if sum(name in other.get("tools", []) for other in tasks) > 1
    }
    progress: list[dict[str, Any]] = []
    used_call_ids: set[str] = set()
    for task in tasks:
        expected_topic = str(task.get("topic") or "").strip().casefold()
        matched: list[dict[str, Any]] = []
        missing: list[str] = []
        failed_tools: list[str] = []
        for name in task.get("tools") or []:
            candidates = [call for call in calls if call.get("name") == name and str(call.get("id")) not in used_call_ids and (
                name not in repeated or expected_topic == str(
                    (call.get("arguments") or {}).get("topic")
                    or (call.get("arguments") or {}).get("concept")
                    or (call.get("arguments") or {}).get("goal") or ""
                ).strip().casefold()
            )]
            done_call = next((call for call in candidates if str(call.get("id")) in successful), None)
            if done_call is not None:
                used_call_ids.add(str(done_call.get("id")))
                matched.append({**successful[str(done_call.get("id"))], "_expected_tool": name})
            elif any(str(call.get("id")) in failed for call in candidates):
                failed_tools.append(name)
            else:
                missing.append(name)
        artifact_refs = [
            ref for observation in matched
            for ref in list(observation.get("artifact_refs") or [])[:5]
        ][:10]
        acceptable_output = bool(matched) and all(
            item.get("artifact_refs") or valid_non_artifact_output(item["_expected_tool"], item.get("output"))
            for item in matched
        )
        status = (
            "succeeded" if not missing and not failed_tools and acceptable_output
            else "failed" if failed_tools
            else "running" if matched
            else "pending"
        )
        progress.append({
            "subtask_id": str(task.get("id") or ""),
            "status": status,
            "artifact_refs": artifact_refs,
            "missing_tools": missing,
            "failed_tools": failed_tools,
        })
    return progress
