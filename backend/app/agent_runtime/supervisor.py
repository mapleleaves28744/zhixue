from __future__ import annotations

import json
from typing import Any, Protocol
from uuid import uuid4

from pydantic import ValidationError

from app.agent_runtime.answer_text import extract_final_answer_text
from app.agent_runtime.state import AgentDecision, PlannedToolCall
from app.agent_runtime import supervisor_intents
from app.llm.schemas import ChatMessage, ToolCall
from app.services.conversation_intent import is_simple_greeting, simple_greeting_answer


class Supervisor(Protocol):
    async def decide(
        self,
        state: dict[str, Any],
        tool_schemas: list[dict[str, Any]],
    ) -> AgentDecision:
        ...


class MiMoSupervisor:
    def __init__(self, provider: object) -> None:
        self.provider = provider

    async def decide(
        self,
        state: dict[str, Any],
        tool_schemas: list[dict[str, Any]],
    ) -> AgentDecision:
        if is_simple_greeting(str(state.get("goal") or "")):
            return AgentDecision(
                status="complete",
                summary="轻量寒暄直接响应。",
                final_answer=simple_greeting_answer(),
            )
        bounded_decision = self._profile_update_only_decision(state, tool_schemas)
        if bounded_decision is not None:
            return bounded_decision
        early_complete = self._deliverables_complete_decision(state, tool_schemas)
        if early_complete is not None:
            return early_complete
        intent_first = self._intent_first_decision(state, tool_schemas)
        if intent_first is not None:
            return self._apply_safety_net(state, tool_schemas, intent_first)
        messages = self._build_messages(state)
        chat_kwargs: dict[str, Any] = {
            "thinking": {"type": "disabled"},
        }
        if tool_schemas:
            chat_kwargs["tools"] = tool_schemas
            chat_kwargs["tool_choice"] = "auto"
        else:
            chat_kwargs["response_format"] = {"type": "json_object"}
        response = await self.provider.chat(messages, **chat_kwargs)
        if response.tool_calls:
            decision = AgentDecision(
                status="continue",
                summary="Supervisor 根据当前目标选择了下一组工具。",
                plan=[f"调用 {item.name}" for item in response.tool_calls],
                tool_calls=[
                    PlannedToolCall(
                        id=item.id or f"call_{uuid4().hex}",
                        name=item.name,
                        arguments=item.arguments,
                    )
                    for item in response.tool_calls
                ],
                reasoning_content=response.reasoning_content,
            )
            return self._apply_safety_net(state, tool_schemas, decision)
        decision = self._parse_decision(response.content)
        decision.reasoning_content = response.reasoning_content
        return self._apply_safety_net(state, tool_schemas, decision)

    def _parse_decision(self, content: str) -> AgentDecision:
        try:
            data = json.loads(content)
            if isinstance(data, dict) and "status" in data:
                data = self._normalize_decision_payload(data)
                decision = AgentDecision.model_validate(data)
                if decision.tool_calls and decision.status == "complete":
                    decision.status = "continue"
                if decision.final_answer:
                    decision.final_answer = extract_final_answer_text(decision.final_answer)
                return decision
            if isinstance(data, dict):
                raw_calls = data.get("tool_calls")
                if isinstance(raw_calls, list) and raw_calls:
                    calls = []
                    for item in raw_calls:
                        if not isinstance(item, dict):
                            continue
                        name = item.get("tool_name") or item.get("name")
                        if not name:
                            continue
                        calls.append(
                            PlannedToolCall(
                                id=str(item.get("id") or f"call_{uuid4().hex}"),
                                name=str(name),
                                arguments=dict(item.get("parameters") or item.get("arguments") or {}),
                            )
                        )
                    if calls:
                        summary = str(data.get("decision") or data.get("summary") or "继续调用专业工具。")
                        return AgentDecision(
                            status="continue",
                            summary=summary[:1000],
                            plan=[summary[:1000]],
                            tool_calls=calls,
                        )
                answer = data.get("final_answer") or data.get("answer")
                if answer:
                    return AgentDecision(
                        status="complete",
                        summary=str(data.get("decision") or data.get("summary") or "任务完成")[:1000],
                        final_answer=str(answer),
                    )
        except (json.JSONDecodeError, ValidationError, TypeError):
            pass
        extracted = extract_final_answer_text(content)
        if extracted:
            return AgentDecision(
                status="complete",
                summary="Supervisor 直接完成回答。",
                final_answer=extracted,
            )
        return AgentDecision(
            status="failed",
            summary="Supervisor 未返回可执行决策。",
            final_answer="智能体未能生成有效计划，请补充目标后重试。",
        )

    def _apply_safety_net(
        self,
        state: dict[str, Any],
        tool_schemas: list[dict[str, Any]],
        decision: AgentDecision,
    ) -> AgentDecision:
        """LLM 决策优先；仅在交付物缺失、显式约束或 LLM 空转时介入。"""
        goal = str(state.get("goal") or "")
        available = self._available_tool_names(tool_schemas)
        completed_tools = self._completed_tool_names(state)
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
            goal,
            is_profile_update_only=self._is_profile_update_only_goal(goal),
        )
        if (
            required_tools == ["answer_course_question"]
            and "answer_course_question" in available
            and "answer_course_question" not in completed_tools
            and "answer_course_question" not in skip_tools
        ):
            return self._force_tool(
                "answer_course_question",
                goal,
                state,
                decision,
                reason="显式课程依据问答统一由可信问答内核完成",
            )

        if decision.tool_calls:
            if decision.status == "complete":
                decision.status = "continue"
            decision.tool_calls = [
                call
                for call in decision.tool_calls
                if call.name not in completed_tools and call.name not in skip_tools
            ]
            if not decision.tool_calls:
                pending_deliverables = self._pending_deliverables(
                    goal, available, completed_tools, skip_tools
                )
                if not pending_deliverables:
                    return AgentDecision(
                        status="complete",
                        summary="所需交付物已全部生成。",
                        final_answer=self._build_completion_answer(state),
                        reasoning_content=decision.reasoning_content,
                    )
                tool_name = pending_deliverables[0]
                label = supervisor_intents.deliverable_label(tool_name)
                return self._force_tool(
                    tool_name,
                    goal,
                    state,
                    decision,
                    reason=f"用户要求的{label}尚未生成，禁止重复调用已完成工具",
                )
            decision.tool_calls = self._filter_tool_calls_for_profile_only(goal, decision.tool_calls)
            decision.tool_calls = self._align_tool_calls_with_deliverables(
                goal,
                completed_tools,
                decision.tool_calls,
                available,
                skip_tools,
                state,
            )
            for call in decision.tool_calls:
                call.arguments = self._safe_arguments(call.name, call.arguments, goal, state)
            if decision.tool_calls:
                return decision
            pending_deliverables = self._pending_deliverables(
                goal, available, completed_tools, skip_tools
            )
            if pending_deliverables:
                tool_name = pending_deliverables[0]
                label = supervisor_intents.deliverable_label(tool_name)
                return self._force_tool(
                    tool_name,
                    goal,
                    state,
                    decision,
                    reason=f"用户要求的{label}尚未生成，安全约束后需补调",
                )

        pending_deliverables = self._pending_deliverables(goal, available, completed_tools, skip_tools)

        hint = self._next_tool_hint(state, available, completed_tools, skip_tools)
        if hint and decision.status == "complete":
            return self._force_tool(hint, goal, state, decision, reason="用户指定工具")

        if (
            decision.status == "complete"
            and self._requires_explicit_retrieval(goal, completed_tools, state, skip_tools)
            and (
                (
                    "answer_course_question" in available
                    and "answer_course_question" not in skip_tools
                )
                or (
                    "search_course_knowledge" in available
                    and "search_course_knowledge" not in skip_tools
                )
            )
        ):
            grounded_tool = (
                "answer_course_question"
                if required_tools == ["answer_course_question"]
                and "answer_course_question" in available
                and "answer_course_question" not in skip_tools
                else "search_course_knowledge"
            )
            return self._force_tool(
                grounded_tool,
                goal,
                state,
                decision,
                reason=(
                    "用户明确要求基于课程资料回答，必须使用可信问答内核"
                    if grounded_tool == "answer_course_question"
                    else "生成多模态产物前必须先检索课程依据"
                ),
            )

        if (
            decision.status == "complete"
            and supervisor_intents.web_search_intent(goal)
            and "search_web" not in completed_tools
            and "search_web" in available
            and "search_web" not in skip_tools
        ):
            return self._force_tool(
                "search_web",
                goal,
                state,
                decision,
                reason="用户要求联网搜索，必须先获取实时网页结果",
            )

        if decision.status == "complete" and pending_deliverables:
            tool_name = pending_deliverables[0]
            label = supervisor_intents.deliverable_label(tool_name)
            return self._force_tool(
                tool_name,
                goal,
                state,
                decision,
                reason=f"用户要求的{label}尚未生成，禁止仅用文字/Markdown 代替",
            )

        if decision.status == "complete" and self._has_wrong_deliverable_only(state, goal):
            pending = self._pending_deliverables(goal, available, completed_tools, skip_tools)
            if pending:
                tool_name = pending[0]
                label = supervisor_intents.deliverable_label(tool_name)
                return self._force_tool(
                    tool_name,
                    goal,
                    state,
                    decision,
                    reason=f"已调用错误工具，需补生成{label}",
                )

        if decision.status == "complete":
            decision.final_answer = self._normalize_completion_answer(state, goal, decision.final_answer)

        if decision.status == "complete" and self._should_use_fallback_planner(
            goal,
            state,
            available,
            completed_tools,
            skip_tools,
            pending_deliverables,
        ):
            fallback = self._fallback_next_tool(goal, available, completed_tools, skip_tools)
            if fallback:
                return self._force_tool(
                    fallback,
                    goal,
                    state,
                    decision,
                    reason=f"LLM 未调用工具，安全网补调 {fallback}",
                )

        return decision

    def _enforce_execution_policy(
        self,
        state: dict[str, Any],
        tool_schemas: list[dict[str, Any]],
        decision: AgentDecision,
    ) -> AgentDecision:
        return self._apply_safety_net(state, tool_schemas, decision)

    @staticmethod
    def _available_tool_names(tool_schemas: list[dict[str, Any]]) -> set[str]:
        return {
            str(item.get("function", {}).get("name"))
            for item in tool_schemas
            if isinstance(item, dict) and item.get("function", {}).get("name")
        }

    @staticmethod
    def _completed_tool_names(state: dict[str, Any]) -> set[str]:
        return {
            str(item.get("tool_name"))
            for item in state.get("observations") or []
            if item.get("success") is True and item.get("tool_name")
        }

    def _pending_deliverables(
        self,
        goal: str,
        available: set[str],
        completed_tools: set[str],
        skip_tools: set[str],
    ) -> list[str]:
        deliverable_set = set(self._required_deliverables(goal))
        ordered = supervisor_intents.plan_required_tools(
            goal,
            is_profile_update_only=self._is_profile_update_only_goal(goal),
        )
        return [
            name
            for name in ordered
            if name in deliverable_set
            and name in available
            and name not in completed_tools
            and name not in skip_tools
        ]

    def _next_tool_hint(
        self,
        state: dict[str, Any],
        available: set[str],
        completed_tools: set[str],
        skip_tools: set[str],
    ) -> str | None:
        for name in reversed(state.get("tool_hints") or []):
            if name in available and name not in completed_tools and name not in skip_tools:
                return str(name)
        return None

    def _requires_explicit_retrieval(
        self,
        goal: str,
        completed_tools: set[str],
        state: dict[str, Any],
        skip_tools: set[str],
    ) -> bool:
        if (
            "search_course_knowledge" in completed_tools
            or "answer_course_question" in completed_tools
            or "search_course_knowledge" in skip_tools
            or "answer_course_question" in skip_tools
        ):
            return False
        if state.get("citations"):
            return False
        explicit = ("基于课程资料", "基于资料", "给出引用", "引用来源", "课程知识库")
        return any(phrase in goal for phrase in explicit)

    def _should_use_fallback_planner(
        self,
        goal: str,
        state: dict[str, Any],
        available: set[str],
        completed_tools: set[str],
        skip_tools: set[str],
        pending_deliverables: list[str],
    ) -> bool:
        if pending_deliverables:
            return False
        if int(state.get("tool_call_count") or 0) > 0:
            return False
        if self._is_profile_update_only_goal(goal):
            return False
        planned = supervisor_intents.plan_required_tools(
            goal,
            is_profile_update_only=False,
        )
        if planned == ["answer_course_question"]:
            return False
        return bool(self._fallback_next_tool(goal, available, completed_tools, skip_tools))

    def _fallback_next_tool(
        self,
        goal: str,
        available: set[str],
        completed_tools: set[str],
        skip_tools: set[str],
    ) -> str | None:
        planned = supervisor_intents.plan_required_tools(
            goal,
            is_profile_update_only=self._is_profile_update_only_goal(goal),
        )
        for name in planned:
            if name in available and name not in completed_tools and name not in skip_tools:
                return name
        return None

    def _force_tool(
        self,
        tool_name: str,
        goal: str,
        state: dict[str, Any],
        decision: AgentDecision,
        *,
        reason: str,
    ) -> AgentDecision:
        return AgentDecision(
            status="continue",
            summary=reason,
            plan=[f"调用 {tool_name}"],
            tool_calls=[
                PlannedToolCall(
                    id=f"call_{uuid4().hex}",
                    name=tool_name,
                    arguments=self._safe_arguments(tool_name, {}, goal, state),
                )
            ],
            reasoning_content=decision.reasoning_content,
        )

    def _filter_tool_calls_for_profile_only(
        self,
        goal: str,
        tool_calls: list[PlannedToolCall],
    ) -> list[PlannedToolCall]:
        if not self._is_profile_update_only_goal(goal):
            return tool_calls
        allowed = {"update_profile_from_dialogue"}
        return [call for call in tool_calls if call.name in allowed]

    def _align_tool_calls_with_deliverables(
        self,
        goal: str,
        completed_tools: set[str],
        tool_calls: list[PlannedToolCall],
        available: set[str],
        skip_tools: set[str],
        state: dict[str, Any],
    ) -> list[PlannedToolCall]:
        pending = self._pending_deliverables(goal, available, completed_tools, skip_tools)
        if not pending or not tool_calls:
            return tool_calls
        primary = pending[0]
        chosen = {call.name for call in tool_calls}
        if primary in chosen:
            return tool_calls
        prep_tools = {"search_course_knowledge", "generate_explanation", "answer_course_question"}
        if primary == "synthesize_speech" and chosen.issubset(prep_tools):
            if "generate_explanation" in chosen and "generate_explanation" not in completed_tools:
                return tool_calls
            if supervisor_intents.should_prepare_speech_script(goal) and "generate_explanation" not in completed_tools:
                return tool_calls
        if chosen.isdisjoint(set(pending)):
            return [
                PlannedToolCall(
                    id=f"call_{uuid4().hex}",
                    name=primary,
                    arguments=self._safe_arguments(primary, {}, goal, state),
                )
            ]
        return tool_calls

    def _deliverables_complete_decision(
        self,
        state: dict[str, Any],
        tool_schemas: list[dict[str, Any]],
    ) -> AgentDecision | None:
        goal = str(state.get("goal") or "")
        required = self._required_deliverables(goal)
        if not required:
            return None
        available = self._available_tool_names(tool_schemas)
        completed_tools = self._completed_tool_names(state)
        skip_tools = set(state.get("skip_tools") or [])
        pending = self._pending_deliverables(goal, available, completed_tools, skip_tools)
        if pending:
            return None
        return AgentDecision(
            status="complete",
            summary="所需交付物已全部生成。",
            final_answer=self._build_completion_answer(state),
        )

    def _build_completion_answer(self, state: dict[str, Any]) -> str:
        goal = str(state.get("goal") or "")
        search_answer = self._build_search_results_answer(state, goal)
        if search_answer:
            return search_answer

        artifacts = state.get("artifacts") or []
        lines = ["所需学习内容已生成，请查看下方产物卡片或资源侧栏。"]
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            title = str(artifact.get("title") or artifact.get("name") or "学习产物")
            subtype = str(artifact.get("subtype") or artifact.get("asset_type") or artifact.get("type") or "")
            if subtype == "image" or artifact.get("mime_type", "").startswith("image/"):
                lines.append(f"- 教学插图：{title}")
            elif subtype in {"mindmap", "diagram"} or artifact.get("type") == "resource":
                lines.append(f"- 知识卡片/资源：{title}")
            elif artifact.get("type") == "quiz":
                lines.append(f"- 练习题：{title}")
            elif artifact.get("type") == "learning_path":
                lines.append(f"- 学习路径：{title}")
            elif artifact.get("type") == "media_asset":
                lines.append(f"- 多模态产物：{title}")
        if len(lines) == 1 and state.get("observations"):
            lines.append("- 相关工具已执行完成，可在执行详情中查看输出。")
        return "\n".join(lines)

    def _build_search_results_answer(self, state: dict[str, Any], goal: str) -> str | None:
        observations = list(state.get("observations") or [])
        for obs in reversed(observations):
            if obs.get("success") is not True:
                continue
            tool_name = str(obs.get("tool_name") or "")
            if tool_name != "answer_course_question":
                continue
            output = obs.get("output")
            if not isinstance(output, dict):
                continue
            for key in ("answer", "content", "summary"):
                value = output.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

        for obs in reversed(observations):
            if obs.get("success") is not True:
                continue
            tool_name = str(obs.get("tool_name") or "")
            if tool_name not in {"search_web", "search_course_knowledge"}:
                continue
            output = obs.get("output")
            if not isinstance(output, dict):
                continue
            return self._format_search_output_answer(tool_name, output, goal)
        return None

    @staticmethod
    def _format_search_output_answer(tool_name: str, output: dict[str, Any], goal: str) -> str:
        query = str(output.get("query") or goal).strip()
        items = output.get("items") or []
        lines: list[str] = []
        if tool_name == "search_web":
            lines.append(f"## 联网搜索：{query}\n")
            message = str(output.get("message") or "").strip()
            if message and output.get("provider") == "mock":
                lines.append(f"_{message}_\n")
        else:
            lines.append(f"## 课程资料检索：{query}\n")

        if not items:
            lines.append("未找到相关结果，请尝试换关键词或补充更具体的描述。")
            return "\n".join(lines).strip()

        lines.append("为你找到以下参考来源：\n")
        for index, item in enumerate(items[:5], start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or f"结果 {index}")
            url = str(item.get("url") or "").strip()
            snippet = str(item.get("snippet") or item.get("content") or "").strip()
            if len(snippet) > 400:
                snippet = snippet[:400].rstrip() + "…"
            lines.append(f"{index}. **{title}**")
            if snippet:
                lines.append(f"   {snippet}")
            if url:
                lines.append(f"   来源：{url}")
            lines.append("")

        if tool_name == "search_web":
            lines.append("> 以上信息来自互联网公开资料，建议结合官方文档进一步核实。")
        else:
            lines.append("> 以上内容来自你的课程资料检索结果。")
        return "\n".join(lines).strip()

    def _profile_update_only_decision(
        self,
        state: dict[str, Any],
        tool_schemas: list[dict[str, Any]],
    ) -> AgentDecision | None:
        goal = str(state.get("goal") or "")
        if not self._is_profile_update_only_goal(goal):
            return None
        available = {
            str(item.get("function", {}).get("name"))
            for item in tool_schemas
            if isinstance(item, dict)
        }
        if "update_profile_from_dialogue" not in available:
            return None
        completed = any(
            item.get("success") is True and item.get("tool_name") == "update_profile_from_dialogue"
            for item in state.get("observations") or []
        )
        if completed:
            return AgentDecision(
                status="complete",
                summary="对话式学习画像已更新。",
                final_answer="已记录你的学习目标、偏好和薄弱点，后续学习建议会参考这些信息。",
            )
        return AgentDecision(
            status="continue",
            summary="本轮仅更新对话式学习画像，不扩张为资源或练习生成任务。",
            plan=["从当前对话提取并更新学习画像"],
            tool_calls=[
                PlannedToolCall(
                    id=f"call_{uuid4().hex}",
                    name="update_profile_from_dialogue",
                    arguments=self._safe_arguments("update_profile_from_dialogue", {}, goal, state),
                )
            ],
        )

    def _intent_first_decision(
        self,
        state: dict[str, Any],
        tool_schemas: list[dict[str, Any]],
    ) -> AgentDecision | None:
        if int(state.get("tool_call_count") or 0) > 0:
            return None
        goal = str(state.get("goal") or "")
        if not supervisor_intents.should_intent_first_route(goal):
            return None
        available = self._available_tool_names(tool_schemas)
        skip_tools = set(state.get("skip_tools") or [])
        planned = self._required_tools(goal)
        if not planned:
            return None
        calls: list[PlannedToolCall] = []
        for name in planned:
            if name not in available or name in skip_tools:
                continue
            calls.append(
                PlannedToolCall(
                    id=f"call_{uuid4().hex}",
                    name=name,
                    arguments=self._safe_arguments(name, {}, goal, state),
                )
            )
        if not calls:
            return None
        primary = calls[-1].name
        return AgentDecision(
            status="continue",
            summary=f"意图识别：优先调用 {supervisor_intents.deliverable_label(primary)}",
            plan=[f"调用 {item.name}" for item in calls],
            tool_calls=calls,
        )

    @staticmethod
    def _has_wrong_deliverable_only(state: dict[str, Any], goal: str) -> bool:
        required = set(supervisor_intents.required_deliverables(goal))
        if not required:
            return False
        completed = {
            str(item.get("tool_name"))
            for item in state.get("observations") or []
            if item.get("success") is True and item.get("tool_name")
        }
        if required & completed:
            return False
        generation = {
            "generate_lesson_video",
            "generate_immersive_classroom",
            "generate_interactive_courseware",
            "generate_storyboard_html",
            "generate_educational_image",
            "generate_diagram",
            "generate_mindmap",
            "generate_explanation",
            "synthesize_speech",
        }
        return bool(completed & generation)

    def _normalize_completion_answer(
        self,
        state: dict[str, Any],
        goal: str,
        answer: str,
    ) -> str:
        observations = list(state.get("observations") or [])
        for obs in reversed(observations):
            if obs.get("success") is not True:
                continue
            tool_name = str(obs.get("tool_name") or "")
            output = obs.get("output") if isinstance(obs.get("output"), dict) else {}
            if tool_name == "generate_interactive_courseware":
                title = str(output.get("title") or "互动课件")
                asset_id = output.get("asset_id") or output.get("media_asset_id")
                return (
                    f"互动课件已生成：{title}\n"
                    f"- 请在下方产物卡片或资源侧栏打开 HTML 课件预览"
                    + (f"\n- asset_id={asset_id}" if asset_id else "")
                )
            if tool_name == "generate_lesson_video":
                job_id = output.get("media_job_id") or output.get("job_id")
                return (
                    "讲解视频任务已提交后台队列，尚未完成渲染。\n"
                    f"- job_id={job_id}\n"
                    "- 请在执行轨迹查看进度；若出现 failed 步骤，说明后台渲染失败，需要重试或改选互动课件。"
                )
            if tool_name == "generate_immersive_classroom":
                job_id = output.get("media_job_id") or output.get("job_id")
                return (
                    "沉浸课堂任务已提交后台队列。\n"
                    f"- job_id={job_id}\n"
                    "- 请在执行轨迹查看 OpenMAIC 生成进度。"
                )
            if tool_name in {"search_web", "search_course_knowledge"}:
                formatted = self._format_search_output_answer(tool_name, output, goal)
                if formatted:
                    return formatted
        search_answer = self._build_search_results_answer(state, goal)
        if search_answer:
            return search_answer
        if supervisor_intents.presentation_intent(goal) and answer:
            if "视频" in answer and "课件" not in answer:
                return self._build_completion_answer(state)
        cleaned = extract_final_answer_text(answer)
        return cleaned or self._build_completion_answer(state)

    def _is_profile_update_only_goal(self, goal: str) -> bool:
        return supervisor_intents.is_profile_update_only_goal(goal)

    def _required_tools(self, goal: str) -> list[str]:
        tools = supervisor_intents.plan_required_tools(
            goal,
            is_profile_update_only=self._is_profile_update_only_goal(goal),
        )
        return self._ensure_knowledge_search_first(goal, tools)

    def _required_deliverables(self, goal: str) -> list[str]:
        return supervisor_intents.required_deliverables(goal)

    def _speech_intent(self, goal: str) -> bool:
        return supervisor_intents.speech_intent(goal)

    def _video_intent(self, goal: str) -> bool:
        return supervisor_intents.video_intent(goal)

    def _extract_topic_from_goal(self, goal: str) -> str:
        return supervisor_intents.extract_topic_from_segment(goal)

    def _topic_for_tool(self, tool_name: str, goal: str, state: dict[str, Any]) -> str:
        tool_topics = state.get("tool_topics") or {}
        topic = str(tool_topics.get(tool_name) or "").strip()
        if topic:
            return topic
        return self._extract_topic_from_goal(goal)

    def _resolve_speech_text(self, state: dict[str, Any], goal: str, text: str | None = None) -> str:
        candidate = str(text or "").strip()
        if candidate and candidate != goal.strip() and len(candidate) >= 40:
            return candidate[:4000]
        for obs in reversed(state.get("observations") or []):
            output = obs.get("output")
            if not isinstance(output, dict):
                continue
            for key in ("content", "text", "answer", "summary"):
                value = output.get(key)
                if isinstance(value, str) and len(value.strip()) >= 40:
                    return value.strip()[:4000]
            chunks = output.get("chunks")
            if isinstance(chunks, list) and chunks:
                merged = "\n".join(
                    str(item.get("content") or item.get("text") or item)
                    for item in chunks[:5]
                    if item is not None
                ).strip()
                if len(merged) >= 40:
                    return merged[:4000]
        topic = self._extract_topic_from_goal(goal)
        return (
            f"你好，下面为你讲解{topic}。"
            f"{topic}是数据结构中的核心知识点，遵循先进先出的原则。"
            f"常见操作包括入队、出队、取队头和判空，在任务调度与广度优先搜索中应用广泛。"
        )[:4000]

    _GENERATION_TOOLS = {
        "generate_learning_path",
        "generate_explanation",
        "generate_quiz",
        "generate_mindmap",
        "generate_diagram",
        "generate_educational_image",
        "generate_lesson_video",
        "generate_immersive_classroom",
        "generate_storyboard_html",
        "generate_interactive_courseware",
        "answer_course_question",
    }

    def _ensure_knowledge_search_first(self, goal: str, tools: list[str]) -> list[str]:
        if self._is_profile_update_only_goal(goal):
            return tools
        needs_grounding = any(name in self._GENERATION_TOOLS for name in tools) or self._should_ground_in_course_materials(goal)
        if needs_grounding and "search_course_knowledge" not in tools:
            return ["search_course_knowledge", *tools]
        return tools

    def _should_ground_in_course_materials(self, goal: str) -> bool:
        keywords = (
            "什么是",
            "讲解",
            "解释",
            "为什么",
            "如何",
            "帮我",
            "BFS",
            "DFS",
            "广度优先",
            "深度优先",
            "排序",
            "队列",
            "栈",
            "二叉树",
            "图",
            "遍历",
            "算法",
            "数据结构",
            "哈希",
            "链表",
        )
        return any(keyword in goal for keyword in keywords)

    def _safe_arguments(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        goal: str,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = dict(arguments)
        state = state or {}
        topic = self._topic_for_tool(tool_name, goal, state)
        defaults: dict[str, dict[str, Any]] = {
            "search_course_knowledge": {"query": topic or goal, "top_k": 10},
            "search_web": {"query": topic or goal, "max_results": 5},
            "answer_course_question": {"question": goal, "top_k": 5},
            "generate_learning_path": {"goal": topic or goal},
            "generate_explanation": {"topic": topic, "requirement": goal},
            "generate_quiz": {"topic": topic},
            "parse_uploaded_document": {},
            "generate_mindmap": {"topic": topic, "scope": "course", "depth": 3},
            "generate_diagram": {"concept": topic, "diagram_type": "flowchart"},
            "generate_educational_image": {
                "topic": topic,
                "image_type": "concept_illustration",
                "style": "clean educational illustration",
                "size": "1280x720",
                "requirement": goal,
            },
            "generate_lesson_video": {
                "topic": topic,
                "duration_seconds": 90,
                "visual_mode": "storyboard",
                "target_level": "undergraduate",
            },
            "generate_immersive_classroom": {
                "topic": topic,
                "learning_goal": topic or goal,
                "generate_video_export": True,
                "enable_images": True,
                "enable_video_clips": False,
                "enable_tts": True,
            },
            "generate_storyboard_html": {
                "topic": topic,
                "duration_seconds": 90,
                "requirement": goal,
            },
            "generate_interactive_courseware": {
                "topic": topic,
                "interaction_type": "stepper",
                "target_level": "undergraduate",
                "requirement": goal,
            },
            "transcribe_audio": {},
            "synthesize_speech": {
                "text": self._resolve_speech_text(state, goal),
                "model_type": "tts",
                "response_format": "wav",
            },
            "update_profile_from_dialogue": {"dialogue_text": goal},
            "review_artifacts": {"content": goal},
            "review_multimodal_asset": {},
        }
        for key, value in defaults.get(tool_name, {}).items():
            if not normalized.get(key):
                normalized[key] = value
        if tool_name == "review_multimodal_asset" and not normalized.get("asset_id"):
            import re

            match = re.search(
                r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                goal,
                flags=re.IGNORECASE,
            )
            if match:
                normalized["asset_id"] = match.group(0)
        if tool_name == "generate_quiz" and normalized.get("question_types"):
            aliases = {
                "选择题": "single_choice",
                "单选题": "single_choice",
                "多选题": "multiple_choice",
                "判断题": "judge",
                "简答题": "short_answer",
                "填空题": "fill_blank",
                "fill_in_blank": "fill_blank",
                "编程题": "coding",
            }
            allowed = {
                "single_choice",
                "multiple_choice",
                "judge",
                "short_answer",
                "fill_blank",
                "coding",
            }
            normalized["question_types"] = [
                aliases.get(str(item), str(item))
                for item in normalized["question_types"]
                if aliases.get(str(item), str(item)) in allowed
            ] or ["single_choice"]
        return normalized

    def _normalize_decision_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(data)
        calls: list[dict[str, Any]] = []
        for item in data.get("tool_calls") or []:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("tool_name") or item.get("tool")
            if not name:
                continue
            calls.append(
                {
                    "id": str(item.get("id") or f"call_{uuid4().hex}"),
                    "name": str(name),
                    "arguments": dict(
                        item.get("arguments") or item.get("parameters") or item.get("args") or {}
                    ),
                }
            )
        normalized["tool_calls"] = calls
        if not normalized.get("plan") and normalized.get("summary"):
            normalized["plan"] = [str(normalized["summary"])]
        return normalized

    def _build_messages(self, state: dict[str, Any]) -> list[ChatMessage]:
        system = (
            "你是智学工坊 Supervisor Agent。你的职责是根据用户目标、历史消息和工具观察，"
            "**直接通过原生 function calling 选择下一步工具**。"
            "优先调用有来源的知识检索工具；工具失败后调整方案，不要重复无效调用。"
            "交付物必须与用户意图一致：语音→synthesize_speech，普通短视频→generate_lesson_video，"
            "沉浸课堂/一键课程→generate_immersive_classroom，"
            "PPT/幻灯片/课件/slides/deck/keynote/网页ppt→generate_interactive_courseware（多页 HTML 互动课件，不是视频），"
            "插图→generate_educational_image，流程图→generate_diagram，思维导图→generate_mindmap，练习→generate_quiz，"
            "纯答疑→answer_course_question，文字讲解资源→generate_explanation。"
            "用户一句话包含多个交付物（如「二叉树 ppt 和队列思维导图」）时，必须分别调用对应工具，"
            "每个工具的 topic/concept 只用该子任务的主题词，不要把整句当 topic。"
            "用户说「讲解 ppt / 做一份幻灯片 / 课件」时，禁止调用 generate_lesson_video。"
            "禁止把文字资源、Markdown 或摘要冒充语音/视频/图片结果。"
            "当用户要求语音时，先准备讲解文本（检索/生成），再 synthesize_speech。"
            "当用户要求插图/知识卡片时：有文生图 API 则 generate_educational_image；"
            "无 API 时同一工具会自动产出简明 Mermaid 知识卡片（思维导图或流程图）。"
            "Mermaid 与文生图均应保持节点/元素简明，复杂知识用多层而非单节点堆字。"
            "只有在任务真正完成、且不需要再调用工具时，才返回纯文本 final_answer。"
            "若仍需工具，请直接发起 tool call，不要只返回 JSON 计划。"
            "不要输出隐式思维链，只输出简洁决策摘要。"
        )
        goal = str(state.get("goal") or "")
        recommended = supervisor_intents.plan_required_tools(
            goal,
            is_profile_update_only=self._is_profile_update_only_goal(goal),
        )
        context = {
            "goal": state.get("goal"),
            "recommended_tools": recommended,
            "recommended_tool_labels": [
                supervisor_intents.deliverable_label(name) for name in recommended
            ],
            "tool_topics": state.get("tool_topics") or supervisor_intents.parse_tool_topics(goal),
            "parsed_intents": state.get("parsed_intents")
            or [
                {"segment": item.segment, "topic": item.topic, "tools": list(item.tools)}
                for item in supervisor_intents.parse_goal_intents(goal)
            ],
            "current_plan": state.get("current_plan") or [],
            "observations": (state.get("observations") or [])[-8:],
            "artifacts": state.get("artifacts") or [],
            "learning_context": state.get("context") or {},
            "iteration_count": state.get("iteration_count") or 0,
        }
        messages = [ChatMessage(role="system", content=system)]
        for item in (state.get("messages") or [])[-12:]:
            messages.append(
                ChatMessage(
                    role=str(item.get("role") or "user"),
                    content=str(item.get("content") or ""),
                )
            )
        prior_tool_calls = state.get("tool_calls") or []
        observations = state.get("observations") or []
        reasoning_content = state.get("protocol_reasoning_content")
        if reasoning_content and prior_tool_calls and observations:
            last_call = prior_tool_calls[-1]
            messages.append(
                ChatMessage(
                    role="assistant",
                    content="",
                    reasoning_content=str(reasoning_content),
                    tool_calls=[
                        ToolCall(
                            id=str(last_call.get("id") or ""),
                            name=str(last_call.get("name") or ""),
                            arguments=dict(last_call.get("arguments") or {}),
                        )
                    ],
                )
            )
            messages.append(
                ChatMessage(
                    role="tool",
                    tool_call_id=str(last_call.get("id") or ""),
                    content=json.dumps(observations[-1], ensure_ascii=False),
                )
            )
        messages.append(
            ChatMessage(
                role="user",
                content=f"当前任务状态：{json.dumps(context, ensure_ascii=False)}",
            )
        )
        return messages
