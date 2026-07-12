from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.agent_runtime import supervisor_intents


def select_tool_schemas(
    state: Mapping[str, Any], tool_schemas: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    available = {str(item.get("function", {}).get("name")): item for item in tool_schemas}
    goal = str(state.get("goal") or "")
    planned = supervisor_intents.plan_required_tools(
        goal,
        is_profile_update_only=supervisor_intents.is_profile_update_only_goal(goal),
    )
    if not planned and _is_course_qa_goal(goal):
        planned = ["search_course_knowledge", "answer_course_question"]
    elif _requires_course_grounding(planned):
        planned = ["search_course_knowledge", *planned]
    names = _dedupe([*planned, *(state.get("tool_hints") or [])])
    skipped = set(state.get("skip_tools") or [])
    available_candidates = [name for name in names if name in available]
    if available_candidates:
        return [available[name] for name in available_candidates if name not in skipped]
    return list(tool_schemas)


def _dedupe(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _requires_course_grounding(tool_names: Sequence[str]) -> bool:
    return any(
        name
        in {
            "answer_course_question",
            "generate_explanation",
            "generate_quiz",
            "generate_mindmap",
            "generate_diagram",
            "generate_educational_image",
            "generate_lesson_video",
            "generate_immersive_classroom",
            "generate_storyboard_html",
            "generate_interactive_courseware",
        }
        for name in tool_names
    )


def _is_course_qa_goal(goal: str) -> bool:
    return any(
        keyword in goal for keyword in ("什么是", "讲解", "解释", "为什么", "如何", "帮我理解")
    )
