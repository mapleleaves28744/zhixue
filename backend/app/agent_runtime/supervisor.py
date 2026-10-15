from __future__ import annotations

import json
from typing import Any, Protocol
from uuid import uuid4

from pydantic import ValidationError

from app.agent_runtime.answer_text import extract_final_answer_text
from app.agent_runtime.intent_contract import NON_ARTIFACT_TOOLS, valid_non_artifact_output, subtask_progress
from app.agent_runtime import supervisor_intents
from app.agent_runtime.supervisor_completion import build_completion_answer, build_search_results_answer, format_search_output_answer, normalize_completion_answer
from app.agent_runtime.supervisor_policy import SupervisorPolicy, _resolve_speech_text, _topic_for_tool, apply_safety_net, safe_arguments
from app.agent_runtime.supervisor_prompt import build_messages
from app.agent_runtime.state import AgentDecision, PlannedToolCall
from app.llm.schemas import ChatMessage
from app.services.conversation_intent import is_simple_greeting, simple_greeting_answer


class Supervisor(Protocol):
    async def decide(self, state: dict[str, Any], tool_schemas: list[dict[str, Any]]) -> AgentDecision: ...


class MiMoSupervisor:
    def __init__(self, provider: object) -> None:
        self.provider = provider
        self._policy = SupervisorPolicy()
        self.last_answer_metadata: dict[str, Any] = {}

    async def decide(self, state: dict[str, Any], tool_schemas: list[dict[str, Any]]) -> AgentDecision:
        self.last_answer_metadata = {}
        goal = str(state.get("goal") or "")
        intent_frame = state.get("intent_frame_v1") or {}
        if intent_frame.get("mode") == "clarify":
            question = str(intent_frame.get("clarification_question") or "请补充要学习的知识点。")
            return AgentDecision(status="complete", summary="等待学生补充学习主题。", final_answer=question)
        if supervisor_intents.video_intent(goal) or supervisor_intents.immersive_classroom_intent(goal):
            return AgentDecision(
                status="complete",
                summary="讲解视频与沉浸课堂生成已下线。",
                final_answer="讲解视频与沉浸课堂生成功能已下线。可以改用文字讲解、练习题或互动课件。",
            )
        if is_simple_greeting(goal):
            return AgentDecision(status="complete", summary="轻量寒暄直接响应。", final_answer=simple_greeting_answer())
        bounded = self._profile_update_only_decision(state, tool_schemas)
        if bounded is not None:
            return bounded
        contract_tools = {
            str(name)
            for task in (state.get("intent_frame_v1") or {}).get("tasks") or []
            for name in task.get("tools") or []
        }
        missing_artifact = next((
            item for item in state.get("observations") or []
            if item.get("success") is True
            and item.get("tool_name") in contract_tools
            and item.get("tool_name") not in NON_ARTIFACT_TOOLS
            and not item.get("artifact_refs")
        ), None)
        missing_text = next((
            item for item in state.get("observations") or []
            if item.get("success") is True
            and item.get("tool_name") in contract_tools & NON_ARTIFACT_TOOLS
            and not valid_non_artifact_output(str(item.get("tool_name")), item.get("output"))
        ), None)
        if missing_artifact is not None or missing_text is not None:
            return AgentDecision(
                status="failed",
                summary="工具未返回可验收的产物或文本。",
                final_answer="本轮任务未完成：工具结果缺少可验收的产物或文本，请查看执行轨迹后重试。",
            )
        if int(state.get("tool_call_count") or 0) > 0:
            pending_topic = self._policy.pending_repeated_topic_tool(
                state, self._policy.available_tool_names(tool_schemas),
            )
            if pending_topic is not None:
                name, topic = pending_topic
                arguments = safe_arguments(name, {}, goal, state)
                field = "concept" if name == "generate_diagram" else "goal" if name == "generate_learning_path" else "topic"
                arguments[field] = topic
                return AgentDecision(
                    status="continue",
                    summary=f"继续完成 {topic} 的独立交付物。",
                    plan=[f"调用 {name}：{topic}"],
                    tool_calls=[PlannedToolCall(id=f"call_{uuid4().hex}", name=name, arguments=arguments)],
                )
            available = self._policy.available_tool_names(tool_schemas)
            tasks = {item["id"]: item for item in intent_frame.get("tasks") or []}
            for progress in subtask_progress(intent_frame, state):
                if progress["status"] == "failed":
                    continue
                task = tasks[progress["subtask_id"]]
                name = next((name for name in progress["missing_tools"] if name in available and name not in set(state.get("skip_tools") or [])), None)
                if name:
                    arguments = safe_arguments(name, {}, str(task.get("segment") or goal), state)
                    field = "concept" if name == "generate_diagram" else "goal" if name == "generate_learning_path" else "query" if name.startswith("search_") else "topic"
                    if field in arguments:
                        arguments[field] = task["topic"]
                    return AgentDecision(status="continue", summary=f"继续完成子任务 {task['id']}。",
                        plan=[f"调用 {name}：{task['topic']}"],
                        tool_calls=[PlannedToolCall(id=f"call_{uuid4().hex}", name=name, arguments=arguments)])
        complete = self._deliverables_complete_decision(state, tool_schemas)
        if complete is not None:
            return complete
        intent = self._intent_first_decision(state, tool_schemas)
        if intent is not None:
            return self._apply_safety_net(state, tool_schemas, intent)
        kwargs: dict[str, Any] = {"thinking": {"type": "disabled"}}
        if tool_schemas:
            kwargs.update(tools=tool_schemas, tool_choice="auto")
        else:
            kwargs["response_format"] = {"type": "json_object"}
        messages = self._build_messages(state, tool_schemas)
        response = await self.provider.chat(messages, **kwargs)
        if getattr(response, "finish_reason", None) in {"length", "error", "aborted"}:
            if getattr(response, "finish_reason", None) == "length":
                response = await self.provider.chat(
                    messages + [
                        ChatMessage(role="system", content="上一轮输出被截断。请用完整、简短的工具参数重新给出决策。")
                    ],
                    **kwargs,
                )
            if getattr(response, "finish_reason", None) in {"length", "error", "aborted"}:
                return AgentDecision(status="failed", summary="模型输出不完整，未执行工具。", final_answer="模型输出不完整，请重试。")
        if response.tool_calls:
            decision = AgentDecision(status="continue", summary="Supervisor 根据当前目标选择了下一组工具。", plan=[f"调用 {item.name}" for item in response.tool_calls], tool_calls=[PlannedToolCall(id=item.id or f"call_{uuid4().hex}", name=item.name, arguments=item.arguments) for item in response.tool_calls], reasoning_content=response.reasoning_content)
        else:
            decision = self._parse_decision(response.content)
            decision.reasoning_content = response.reasoning_content
        final = self._apply_safety_net(state, tool_schemas, decision)
        if decision.status == "complete" and final.status == "complete" and final.final_answer == decision.final_answer:
            self.last_answer_metadata = {
                "model": response.model,
                "provider": response.provider,
                "fallback_used": bool((response.raw or {}).get("fallback_used")),
            }
        return final

    def _parse_decision(self, content: str) -> AgentDecision:
        try:
            data = json.loads(content)
            if isinstance(data, dict) and "status" in data:
                decision = AgentDecision.model_validate(self._normalize_decision_payload(data))
                if decision.tool_calls and decision.status == "complete": decision.status = "continue"
                if decision.final_answer: decision.final_answer = extract_final_answer_text(decision.final_answer)
                return decision
            if isinstance(data, dict):
                calls = [PlannedToolCall(id=str(item.get("id") or f"call_{uuid4().hex}"), name=str(item.get("tool_name") or item.get("name")), arguments=dict(item.get("parameters") or item.get("arguments") or {})) for item in data.get("tool_calls") or [] if isinstance(item, dict) and (item.get("tool_name") or item.get("name"))]
                if calls:
                    summary = str(data.get("decision") or data.get("summary") or "继续调用专业工具。")
                    return AgentDecision(status="continue", summary=summary[:1000], plan=[summary[:1000]], tool_calls=calls)
                answer = data.get("final_answer") or data.get("answer")
                if answer: return AgentDecision(status="complete", summary=str(data.get("decision") or data.get("summary") or "任务完成")[:1000], final_answer=str(answer))
        except (json.JSONDecodeError, ValidationError, TypeError):
            pass
        answer = extract_final_answer_text(content)
        return AgentDecision(status="complete", summary="Supervisor 直接完成回答。", final_answer=answer) if answer else AgentDecision(status="failed", summary="Supervisor 未返回可执行决策。", final_answer="智能体未能生成有效计划，请补充目标后重试。")

    def _normalize_decision_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(data); calls = []
        for item in data.get("tool_calls") or []:
            if isinstance(item, dict) and (name := item.get("name") or item.get("tool_name") or item.get("tool")):
                calls.append({"id": str(item.get("id") or f"call_{uuid4().hex}"), "name": str(name), "arguments": dict(item.get("arguments") or item.get("parameters") or item.get("args") or {})})
        normalized["tool_calls"] = calls
        if not normalized.get("plan") and normalized.get("summary"): normalized["plan"] = [str(normalized["summary"])]
        return normalized

    def _apply_safety_net(self, state: dict[str, Any], schemas: list[dict[str, Any]], decision: AgentDecision) -> AgentDecision: return apply_safety_net(self._policy, state, schemas, decision)
    def _enforce_execution_policy(self, state: dict[str, Any], schemas: list[dict[str, Any]], decision: AgentDecision) -> AgentDecision: return self._apply_safety_net(state, schemas, decision)
    def _available_tool_names(self, schemas: list[dict[str, Any]]) -> set[str]: return self._policy.available_tool_names(schemas)
    def _completed_tool_names(self, state: dict[str, Any]) -> set[str]: return self._policy.completed_tool_names(state)
    def _pending_deliverables(self, goal: str, available: set[str], completed: set[str], skip: set[str]) -> list[str]: return self._policy.pending_deliverables(goal, available, completed, skip)
    def _next_tool_hint(self, state: dict[str, Any], available: set[str], completed: set[str], skip: set[str]) -> str | None: return self._policy.next_tool_hint(state, available, completed, skip)
    def _requires_explicit_retrieval(self, goal: str, completed: set[str], state: dict[str, Any], skip: set[str]) -> bool: return self._policy.requires_explicit_retrieval(goal, completed, state, skip)
    def _should_use_fallback_planner(self, goal: str, state: dict[str, Any], available: set[str], completed: set[str], skip: set[str], pending: list[str]) -> bool: return self._policy.should_use_fallback_planner(goal, state, available, completed, skip, pending)
    def _fallback_next_tool(self, goal: str, available: set[str], completed: set[str], skip: set[str]) -> str | None: return self._policy.fallback_next_tool(goal, available, completed, skip)
    def _force_tool(self, name: str, goal: str, state: dict[str, Any], decision: AgentDecision, *, reason: str) -> AgentDecision: return self._policy.force_tool(name, goal, state, decision, reason=reason)
    def _filter_tool_calls_for_profile_only(self, goal: str, calls: list[PlannedToolCall]) -> list[PlannedToolCall]: return self._policy.filter_tool_calls_for_profile_only(goal, calls)
    def _align_tool_calls_with_deliverables(self, goal: str, completed: set[str], calls: list[PlannedToolCall], available: set[str], skip: set[str], state: dict[str, Any]) -> list[PlannedToolCall]: return self._policy.align_tool_calls_with_deliverables(goal, completed, calls, available, skip, state)
    def _deliverables_complete_decision(self, state: dict[str, Any], schemas: list[dict[str, Any]]) -> AgentDecision | None: return self._policy.deliverables_complete_decision(state, schemas)
    def _profile_update_only_decision(self, state: dict[str, Any], schemas: list[dict[str, Any]]) -> AgentDecision | None: return self._policy.profile_update_only_decision(state, schemas)
    def _intent_first_decision(self, state: dict[str, Any], schemas: list[dict[str, Any]]) -> AgentDecision | None: return self._policy.intent_first_decision(state, schemas)
    def _has_wrong_deliverable_only(self, state: dict[str, Any], goal: str) -> bool: return self._policy.has_wrong_deliverable_only(state, goal)
    def _normalize_completion_answer(self, state: dict[str, Any], goal: str, answer: str) -> str: return normalize_completion_answer(state, goal, answer)
    def _build_completion_answer(self, state: dict[str, Any]) -> str: return build_completion_answer(state)
    def _build_search_results_answer(self, state: dict[str, Any], goal: str) -> str | None: return build_search_results_answer(state, goal)
    @staticmethod
    def _format_search_output_answer(name: str, output: dict[str, Any], goal: str) -> str: return format_search_output_answer(name, output, goal)
    def _is_profile_update_only_goal(self, goal: str) -> bool: return self._policy.is_profile_update_only_goal(goal)
    def _required_tools(self, goal: str) -> list[str]: return self._policy.required_tools(goal)
    def _required_deliverables(self, goal: str) -> list[str]: return self._policy.required_deliverables(goal)
    def _speech_intent(self, goal: str) -> bool: return supervisor_intents.speech_intent(goal)
    def _video_intent(self, goal: str) -> bool: return supervisor_intents.video_intent(goal)
    def _extract_topic_from_goal(self, goal: str) -> str: return supervisor_intents.extract_topic_from_segment(goal)
    def _topic_for_tool(self, name: str, goal: str, state: dict[str, Any]) -> str: return _topic_for_tool(name, goal, state)
    def _resolve_speech_text(self, state: dict[str, Any], goal: str, text: str | None = None) -> str: return _resolve_speech_text(state, goal, text)
    def _safe_arguments(self, name: str, args: dict[str, Any], goal: str, state: dict[str, Any] | None = None) -> dict[str, Any]: return safe_arguments(name, args, goal, state)
    def _build_messages(self, state: dict[str, Any], tool_schemas: list[dict[str, Any]] | None = None) -> list[ChatMessage]:
        from app.services.context_budget import estimate_tokens

        schema_reserve = estimate_tokens(json.dumps(tool_schemas, ensure_ascii=False)) if tool_schemas else 0
        return build_messages(state, schema_token_reserve=schema_reserve)
