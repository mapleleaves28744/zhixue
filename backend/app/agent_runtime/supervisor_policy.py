from __future__ import annotations

import re
from typing import Any, Protocol

from app.agent_runtime import supervisor_intents
from app.agent_runtime.state import AgentDecision, PlannedToolCall
from app.agent_runtime.supervisor_completion import build_completion_answer, normalize_completion_answer
from uuid import uuid4


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


class SupervisorPolicy:
    _GENERATION_TOOLS = {"generate_learning_path", "generate_explanation", "generate_quiz", "generate_mindmap", "generate_diagram", "generate_educational_image", "generate_lesson_video", "generate_immersive_classroom", "generate_storyboard_html", "generate_interactive_courseware", "answer_course_question"}

    @staticmethod
    def available_tool_names(tool_schemas: list[dict[str, Any]]) -> set[str]:
        return {str(item.get("function", {}).get("name")) for item in tool_schemas if isinstance(item, dict) and item.get("function", {}).get("name")}

    @staticmethod
    def completed_tool_names(state: dict[str, Any]) -> set[str]:
        return {str(item.get("tool_name")) for item in state.get("observations") or [] if item.get("success") is True and item.get("tool_name")}

    @staticmethod
    def is_profile_update_only_goal(goal: str) -> bool:
        return supervisor_intents.is_profile_update_only_goal(goal)

    def required_deliverables(self, goal: str) -> list[str]:
        return supervisor_intents.required_deliverables(goal)

    def required_tools(self, goal: str) -> list[str]:
        tools = supervisor_intents.plan_required_tools(goal, is_profile_update_only=self.is_profile_update_only_goal(goal))
        if self.is_profile_update_only_goal(goal):
            return tools
        needs_grounding = any(name in self._GENERATION_TOOLS for name in tools) or self.should_ground_in_course_materials(goal)
        return ["search_course_knowledge", *tools] if needs_grounding and "search_course_knowledge" not in tools else tools

    def pending_deliverables(self, goal: str, available: set[str], completed_tools: set[str], skip_tools: set[str]) -> list[str]:
        deliverable_set = set(self.required_deliverables(goal))
        ordered = supervisor_intents.plan_required_tools(goal, is_profile_update_only=self.is_profile_update_only_goal(goal))
        return [name for name in ordered if name in deliverable_set and name in available and name not in completed_tools and name not in skip_tools]

    @staticmethod
    def next_tool_hint(state: dict[str, Any], available: set[str], completed_tools: set[str], skip_tools: set[str]) -> str | None:
        return next((str(name) for name in reversed(state.get("tool_hints") or []) if name in available and name not in completed_tools and name not in skip_tools), None)

    @staticmethod
    def requires_explicit_retrieval(goal: str, completed_tools: set[str], state: dict[str, Any], skip_tools: set[str]) -> bool:
        if {"search_course_knowledge", "answer_course_question"} & (completed_tools | skip_tools) or state.get("citations"):
            return False
        return any(phrase in goal for phrase in ("基于课程资料", "基于资料", "给出引用", "引用来源", "课程知识库"))

    def fallback_next_tool(self, goal: str, available: set[str], completed_tools: set[str], skip_tools: set[str]) -> str | None:
        return next((name for name in self.required_tools(goal) if name in available and name not in completed_tools and name not in skip_tools), None)

    def should_use_fallback_planner(self, goal: str, state: dict[str, Any], available: set[str], completed_tools: set[str], skip_tools: set[str], pending: list[str]) -> bool:
        if pending or int(state.get("tool_call_count") or 0) > 0 or self.is_profile_update_only_goal(goal):
            return False
        return supervisor_intents.plan_required_tools(goal, is_profile_update_only=False) != ["answer_course_question"] and bool(self.fallback_next_tool(goal, available, completed_tools, skip_tools))

    def force_tool(self, tool_name: str, goal: str, state: dict[str, Any], decision: AgentDecision, *, reason: str) -> AgentDecision:
        return AgentDecision(status="continue", summary=reason, plan=[f"调用 {tool_name}"], tool_calls=[PlannedToolCall(id=f"call_{uuid4().hex}", name=tool_name, arguments=safe_arguments(tool_name, {}, goal, state))], reasoning_content=decision.reasoning_content)

    def filter_tool_calls_for_profile_only(self, goal: str, calls: list[PlannedToolCall]) -> list[PlannedToolCall]:
        return [call for call in calls if call.name == "update_profile_from_dialogue"] if self.is_profile_update_only_goal(goal) else calls

    def align_tool_calls_with_deliverables(self, goal: str, completed: set[str], calls: list[PlannedToolCall], available: set[str], skip: set[str], state: dict[str, Any]) -> list[PlannedToolCall]:
        pending = self.pending_deliverables(goal, available, completed, skip)
        if not pending or not calls or pending[0] in {call.name for call in calls}:
            return calls
        chosen = {call.name for call in calls}
        prep = {"search_course_knowledge", "generate_explanation", "answer_course_question"}
        if pending[0] == "synthesize_speech" and chosen.issubset(prep) and ("generate_explanation" in chosen and "generate_explanation" not in completed or supervisor_intents.should_prepare_speech_script(goal) and "generate_explanation" not in completed):
            return calls
        return [PlannedToolCall(id=f"call_{uuid4().hex}", name=pending[0], arguments=safe_arguments(pending[0], {}, goal, state))] if chosen.isdisjoint(set(pending)) else calls

    def deliverables_complete_decision(self, state: dict[str, Any], schemas: list[dict[str, Any]]) -> AgentDecision | None:
        goal = str(state.get("goal") or "")
        if not self.required_deliverables(goal):
            return None
        if self.pending_deliverables(goal, self.available_tool_names(schemas), self.completed_tool_names(state), set(state.get("skip_tools") or [])):
            return None
        return AgentDecision(status="complete", summary="所需交付物已全部生成。", final_answer=build_completion_answer(state))

    def profile_update_only_decision(self, state: dict[str, Any], schemas: list[dict[str, Any]]) -> AgentDecision | None:
        goal = str(state.get("goal") or "")
        if not self.is_profile_update_only_goal(goal) or "update_profile_from_dialogue" not in self.available_tool_names(schemas):
            return None
        if "update_profile_from_dialogue" in self.completed_tool_names(state):
            return AgentDecision(status="complete", summary="对话式学习画像已更新。", final_answer="已记录你的学习目标、偏好和薄弱点，后续学习建议会参考这些信息。")
        return self.force_tool("update_profile_from_dialogue", goal, state, AgentDecision(status="continue", summary="本轮仅更新对话式学习画像，不扩张为资源或练习生成任务。"), reason="本轮仅更新对话式学习画像，不扩张为资源或练习生成任务。")

    def intent_first_decision(self, state: dict[str, Any], schemas: list[dict[str, Any]]) -> AgentDecision | None:
        goal = str(state.get("goal") or "")
        if int(state.get("tool_call_count") or 0) > 0 or not supervisor_intents.should_intent_first_route(goal):
            return None
        available, skip = self.available_tool_names(schemas), set(state.get("skip_tools") or [])
        calls = [PlannedToolCall(id=f"call_{uuid4().hex}", name=name, arguments=safe_arguments(name, {}, goal, state)) for name in self.required_tools(goal) if name in available and name not in skip]
        return AgentDecision(status="continue", summary=f"意图识别：优先调用 {supervisor_intents.deliverable_label(calls[-1].name)}", plan=[f"调用 {item.name}" for item in calls], tool_calls=calls) if calls else None

    @staticmethod
    def has_wrong_deliverable_only(state: dict[str, Any], goal: str) -> bool:
        required = set(supervisor_intents.required_deliverables(goal))
        completed = {str(item.get("tool_name")) for item in state.get("observations") or [] if item.get("success") is True and item.get("tool_name")}
        generation = {"generate_lesson_video", "generate_immersive_classroom", "generate_interactive_courseware", "generate_storyboard_html", "generate_educational_image", "generate_diagram", "generate_mindmap", "generate_explanation", "synthesize_speech"}
        return bool(required) and not bool(required & completed) and bool(completed & generation)

    @staticmethod
    def should_ground_in_course_materials(goal: str) -> bool:
        return any(keyword in goal for keyword in ("什么是", "讲解", "解释", "为什么", "如何", "帮我", "BFS", "DFS", "广度优先", "深度优先", "排序", "队列", "栈", "二叉树", "图", "遍历", "算法", "数据结构", "哈希", "链表"))


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


SupervisorPolicy._available_tool_names = staticmethod(SupervisorPolicy.available_tool_names)
SupervisorPolicy._completed_tool_names = staticmethod(SupervisorPolicy.completed_tool_names)
SupervisorPolicy._is_profile_update_only_goal = staticmethod(SupervisorPolicy.is_profile_update_only_goal)
SupervisorPolicy._force_tool = SupervisorPolicy.force_tool
SupervisorPolicy._pending_deliverables = SupervisorPolicy.pending_deliverables
SupervisorPolicy._filter_tool_calls_for_profile_only = SupervisorPolicy.filter_tool_calls_for_profile_only
SupervisorPolicy._align_tool_calls_with_deliverables = SupervisorPolicy.align_tool_calls_with_deliverables
SupervisorPolicy._safe_arguments = staticmethod(safe_arguments)
SupervisorPolicy._next_tool_hint = staticmethod(SupervisorPolicy.next_tool_hint)
SupervisorPolicy._requires_explicit_retrieval = staticmethod(SupervisorPolicy.requires_explicit_retrieval)
SupervisorPolicy._has_wrong_deliverable_only = staticmethod(SupervisorPolicy.has_wrong_deliverable_only)
SupervisorPolicy._normalize_completion_answer = staticmethod(normalize_completion_answer)
SupervisorPolicy._should_use_fallback_planner = SupervisorPolicy.should_use_fallback_planner
SupervisorPolicy._fallback_next_tool = SupervisorPolicy.fallback_next_tool
SupervisorPolicy._build_completion_answer = staticmethod(build_completion_answer)


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
