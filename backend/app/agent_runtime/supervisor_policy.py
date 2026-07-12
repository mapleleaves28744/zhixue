from __future__ import annotations

import re
from typing import Any, Protocol

from app.agent_runtime import supervisor_intents
from app.agent_runtime.state import AgentDecision


def _topic_for_tool(tool_name: str, goal: str, state: dict[str, Any]) -> str:
    tool_topics = state.get("tool_topics") or {}
    topic = str(tool_topics.get(tool_name) or "").strip()
    return topic or supervisor_intents.extract_topic_from_segment(goal)


def _resolve_speech_text(state: dict[str, Any], goal: str, text: str | None = None) -> str:
    candidate = str(text or "").strip()
    if candidate and candidate != goal.strip() and len(candidate) >= 40:
        return candidate[:4000]
    for observation in reversed(state.get("observations") or []):
        output = observation.get("output")
        if not isinstance(output, dict):
            continue
        for key in ("content", "text", "answer", "summary"):
            value = output.get(key)
            if isinstance(value, str) and len(value.strip()) >= 40:
                return value.strip()[:4000]
        chunks = output.get("chunks")
        if isinstance(chunks, list) and chunks:
            merged = "\n".join(str(item.get("content") or item.get("text") or item) for item in chunks[:5] if item is not None).strip()
            if len(merged) >= 40:
                return merged[:4000]
    topic = supervisor_intents.extract_topic_from_segment(goal)
    return f"你好，下面为你讲解{topic}。{topic}是数据结构中的核心知识点，遵循先进先出的原则。常见操作包括入队、出队、取队头和判空，在任务调度与广度优先搜索中应用广泛。"[:4000]


def safe_arguments(
    tool_name: str,
    arguments: dict[str, Any],
    goal: str,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = dict(arguments)
    state = state or {}
    topic = _topic_for_tool(tool_name, goal, state)
    defaults: dict[str, dict[str, Any]] = {
        "search_course_knowledge": {"query": topic or goal, "top_k": 10},
        "search_web": {"query": topic or goal, "max_results": 5},
        "answer_course_question": {"question": goal, "top_k": 5},
        "generate_learning_path": {"goal": topic or goal}, "generate_explanation": {"topic": topic, "requirement": goal},
        "generate_quiz": {"topic": topic}, "parse_uploaded_document": {},
        "generate_mindmap": {"topic": topic, "scope": "course", "depth": 3},
        "generate_diagram": {"concept": topic, "diagram_type": "flowchart"},
        "generate_educational_image": {"topic": topic, "image_type": "concept_illustration", "style": "clean educational illustration", "size": "1280x720", "requirement": goal},
        "generate_lesson_video": {"topic": topic, "duration_seconds": 90, "visual_mode": "storyboard", "target_level": "undergraduate"},
        "generate_immersive_classroom": {"topic": topic, "learning_goal": topic or goal, "generate_video_export": True, "enable_images": True, "enable_video_clips": False, "enable_tts": True},
        "generate_storyboard_html": {"topic": topic, "duration_seconds": 90, "requirement": goal},
        "generate_interactive_courseware": {"topic": topic, "interaction_type": "stepper", "target_level": "undergraduate", "requirement": goal},
        "transcribe_audio": {}, "synthesize_speech": {"text": _resolve_speech_text(state, goal), "model_type": "tts", "response_format": "wav"},
        "update_profile_from_dialogue": {"dialogue_text": goal}, "review_artifacts": {"content": goal}, "review_multimodal_asset": {},
    }
    for key, value in defaults.get(tool_name, {}).items():
        if not normalized.get(key):
            normalized[key] = value
    if tool_name == "review_multimodal_asset" and not normalized.get("asset_id"):
        match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", goal, flags=re.IGNORECASE)
        if match:
            normalized["asset_id"] = match.group(0)
    if tool_name == "generate_quiz" and normalized.get("question_types"):
        aliases = {"选择题": "single_choice", "单选题": "single_choice", "多选题": "multiple_choice", "判断题": "judge", "简答题": "short_answer", "填空题": "fill_blank", "fill_in_blank": "fill_blank", "编程题": "coding"}
        allowed = {"single_choice", "multiple_choice", "judge", "short_answer", "fill_blank", "coding"}
        normalized["question_types"] = [aliases.get(str(item), str(item)) for item in normalized["question_types"] if aliases.get(str(item), str(item)) in allowed] or ["single_choice"]
    return normalized


class _PolicyHost(Protocol):
    def _available_tool_names(self, tool_schemas: list[dict[str, Any]]) -> set[str]: ...
    def _completed_tool_names(self, state: dict[str, Any]) -> set[str]: ...
    def _is_profile_update_only_goal(self, goal: str) -> bool: ...
    def _force_tool(self, tool_name: str, goal: str, state: dict[str, Any], decision: AgentDecision, *, reason: str) -> AgentDecision: ...
    def _pending_deliverables(self, goal: str, available: set[str], completed_tools: set[str], skip_tools: set[str]) -> list[str]: ...
    def _filter_tool_calls_for_profile_only(self, goal: str, tool_calls: list[Any]) -> list[Any]: ...
    def _align_tool_calls_with_deliverables(self, goal: str, completed_tools: set[str], tool_calls: list[Any], available: set[str], skip_tools: set[str], state: dict[str, Any]) -> list[Any]: ...
    def _safe_arguments(self, tool_name: str, arguments: dict[str, Any], goal: str, state: dict[str, Any] | None = None) -> dict[str, Any]: ...
    def _next_tool_hint(self, state: dict[str, Any], available: set[str], completed_tools: set[str], skip_tools: set[str]) -> str | None: ...
    def _requires_explicit_retrieval(self, goal: str, completed_tools: set[str], state: dict[str, Any], skip_tools: set[str]) -> bool: ...
    def _has_wrong_deliverable_only(self, state: dict[str, Any], goal: str) -> bool: ...
    def _normalize_completion_answer(self, state: dict[str, Any], goal: str, answer: str) -> str: ...
    def _should_use_fallback_planner(self, goal: str, state: dict[str, Any], available: set[str], completed_tools: set[str], skip_tools: set[str], pending_deliverables: list[str]) -> bool: ...
    def _fallback_next_tool(self, goal: str, available: set[str], completed_tools: set[str], skip_tools: set[str]) -> str | None: ...
    def _build_completion_answer(self, state: dict[str, Any]) -> str: ...


def apply_safety_net(
    host: _PolicyHost,
    state: dict[str, Any],
    tool_schemas: list[dict[str, Any]],
    decision: AgentDecision,
) -> AgentDecision:
    """Apply the deterministic safety boundary around an LLM decision."""
    goal = str(state.get("goal") or "")
    available = host._available_tool_names(tool_schemas)
    completed_tools = host._completed_tool_names(state)
    skip_tools = set(state.get("skip_tools") or [])
    observations = list(state.get("observations") or [])
    if observations and observations[-1].get("success") is False:
        err = str(observations[-1].get("error_message") or "工具执行失败")
        return AgentDecision(
            status="failed",
            summary="工具执行失败，已停止本轮任务。",
            final_answer=(
                f"生成未成功：{err}\n\n"
                "请查看上方执行轨迹中的失败步骤；若是视频渲染报错，可改选「互动课件/PPT」或稍后重试。"
            ),
            reasoning_content=decision.reasoning_content,
        )

    required_tools = supervisor_intents.plan_required_tools(
        goal, is_profile_update_only=host._is_profile_update_only_goal(goal)
    )
    if required_tools == ["answer_course_question"] and "answer_course_question" in available and "answer_course_question" not in completed_tools and "answer_course_question" not in skip_tools:
        return host._force_tool("answer_course_question", goal, state, decision, reason="显式课程依据问答统一由可信问答内核完成")

    if decision.tool_calls:
        if decision.status == "complete":
            decision.status = "continue"
        decision.tool_calls = [
            call for call in decision.tool_calls
            if call.name not in completed_tools and call.name not in skip_tools
        ]
        if not decision.tool_calls:
            pending = host._pending_deliverables(goal, available, completed_tools, skip_tools)
            if not pending:
                return AgentDecision(status="complete", summary="所需交付物已全部生成。", final_answer=host._build_completion_answer(state), reasoning_content=decision.reasoning_content)
            tool_name = pending[0]
            return host._force_tool(tool_name, goal, state, decision, reason=f"用户要求的{supervisor_intents.deliverable_label(tool_name)}尚未生成，禁止重复调用已完成工具")
        decision.tool_calls = host._filter_tool_calls_for_profile_only(goal, decision.tool_calls)
        decision.tool_calls = host._align_tool_calls_with_deliverables(goal, completed_tools, decision.tool_calls, available, skip_tools, state)
        for call in decision.tool_calls:
            call.arguments = host._safe_arguments(call.name, call.arguments, goal, state)
        if decision.tool_calls:
            return decision
        pending = host._pending_deliverables(goal, available, completed_tools, skip_tools)
        if pending:
            tool_name = pending[0]
            return host._force_tool(tool_name, goal, state, decision, reason=f"用户要求的{supervisor_intents.deliverable_label(tool_name)}尚未生成，安全约束后需补调")

    pending = host._pending_deliverables(goal, available, completed_tools, skip_tools)
    hint = host._next_tool_hint(state, available, completed_tools, skip_tools)
    if hint and decision.status == "complete":
        return host._force_tool(hint, goal, state, decision, reason="用户指定工具")
    if decision.status == "complete" and host._requires_explicit_retrieval(goal, completed_tools, state, skip_tools) and (("answer_course_question" in available and "answer_course_question" not in skip_tools) or ("search_course_knowledge" in available and "search_course_knowledge" not in skip_tools)):
        grounded_tool = "answer_course_question" if required_tools == ["answer_course_question"] and "answer_course_question" in available and "answer_course_question" not in skip_tools else "search_course_knowledge"
        return host._force_tool(grounded_tool, goal, state, decision, reason="用户明确要求基于课程资料回答，必须使用可信问答内核" if grounded_tool == "answer_course_question" else "生成多模态产物前必须先检索课程依据")
    if decision.status == "complete" and supervisor_intents.web_search_intent(goal) and "search_web" not in completed_tools and "search_web" in available and "search_web" not in skip_tools:
        return host._force_tool("search_web", goal, state, decision, reason="用户要求联网搜索，必须先获取实时网页结果")
    if decision.status == "complete" and pending:
        tool_name = pending[0]
        return host._force_tool(tool_name, goal, state, decision, reason=f"用户要求的{supervisor_intents.deliverable_label(tool_name)}尚未生成，禁止仅用文字/Markdown 代替")
    if decision.status == "complete" and host._has_wrong_deliverable_only(state, goal):
        wrong_pending = host._pending_deliverables(goal, available, completed_tools, skip_tools)
        if wrong_pending:
            tool_name = wrong_pending[0]
            return host._force_tool(tool_name, goal, state, decision, reason=f"已调用错误工具，需补生成{supervisor_intents.deliverable_label(tool_name)}")
    if decision.status == "complete":
        decision.final_answer = host._normalize_completion_answer(state, goal, decision.final_answer)
    if decision.status == "complete" and host._should_use_fallback_planner(goal, state, available, completed_tools, skip_tools, pending):
        fallback = host._fallback_next_tool(goal, available, completed_tools, skip_tools)
        if fallback:
            return host._force_tool(fallback, goal, state, decision, reason=f"LLM 未调用工具，安全网补调 {fallback}")
    return decision
