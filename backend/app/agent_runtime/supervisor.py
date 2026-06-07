from __future__ import annotations

import json
from typing import Any, Protocol
from uuid import uuid4

from pydantic import ValidationError

from app.agent_runtime.state import AgentDecision, PlannedToolCall
from app.llm.schemas import ChatMessage, ToolCall


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
        messages = self._build_messages(state)
        response = await self.provider.chat(
            messages,
            tools=tool_schemas,
            tool_choice="auto",
            response_format={"type": "json_object"},
            thinking={"type": "disabled"},
        )
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
            return self._enforce_execution_policy(state, tool_schemas, decision)
        decision = self._parse_decision(response.content)
        decision.reasoning_content = response.reasoning_content
        return self._enforce_execution_policy(state, tool_schemas, decision)

    def _parse_decision(self, content: str) -> AgentDecision:
        try:
            data = json.loads(content)
            if isinstance(data, dict) and "status" in data:
                data = self._normalize_decision_payload(data)
                decision = AgentDecision.model_validate(data)
                if decision.tool_calls and decision.status == "complete":
                    decision.status = "continue"
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
        if content.strip():
            return AgentDecision(
                status="complete",
                summary="Supervisor 直接完成回答。",
                final_answer=content.strip(),
            )
        return AgentDecision(
            status="failed",
            summary="Supervisor 未返回可执行决策。",
            final_answer="智能体未能生成有效计划，请补充目标后重试。",
        )

    def _enforce_execution_policy(
        self,
        state: dict[str, Any],
        tool_schemas: list[dict[str, Any]],
        decision: AgentDecision,
    ) -> AgentDecision:
        goal = str(state.get("goal") or "")
        available = {
            str(item.get("function", {}).get("name"))
            for item in tool_schemas
            if isinstance(item, dict)
        }
        if decision.tool_calls:
            if decision.status == "complete":
                decision.status = "continue"
            for call in decision.tool_calls:
                call.arguments = self._safe_arguments(call.name, call.arguments, goal)
            return decision

        completed_tools = {
            str(item.get("tool_name"))
            for item in state.get("observations") or []
            if item.get("success") is True and item.get("tool_name")
        }
        missing = [
            name
            for name in self._required_tools(goal)
            if name in available and name not in completed_tools
        ]
        if missing:
            tool_name = missing[0]
            return AgentDecision(
                status="continue",
                summary=f"任务明确要求执行 {tool_name}，继续调用对应专业工具。",
                plan=[f"调用 {name}" for name in missing],
                tool_calls=[
                    PlannedToolCall(
                        id=f"call_{uuid4().hex}",
                        name=tool_name,
                        arguments=self._safe_arguments(tool_name, {}, goal),
                    )
                ],
                reasoning_content=decision.reasoning_content,
            )
        return decision

    def _required_tools(self, goal: str) -> list[str]:
        rules = [
            (
                "search_course_knowledge",
                ("检索", "课程资料", "课程知识库", "基于资料", "基于课程", "引用", "来源"),
            ),
            (
                "generate_learning_path",
                ("学习计划", "学习路径", "复习计划", "安排一周", "安排三天", "制定一个"),
            ),
            ("generate_explanation", ("讲解资料", "配套讲解", "生成一份", "生成讲解")),
            ("generate_quiz", ("练习题", "生成练习", "生成一组练习", "配套练习")),
            ("analyze_learning_diagnosis", ("薄弱点", "错误模式", "学习诊断")),
            ("refresh_recommendations", ("推荐下一步", "推荐学习内容", "刷新推荐")),
            ("rebuild_profile", ("学习画像", "重建画像", "重新整理我的学习画像")),
            ("reflect_learning_memory", ("长期学习记忆", "反思最近学习", "沉淀有价值")),
            ("review_artifacts", ("来源、幻觉和风险审查", "审查学习产物", "审核学习产物")),
            ("apply_evolution_strategy", ("应用最新的一条自进化策略", "应用自进化策略")),
        ]
        return [name for name, keywords in rules if any(keyword in goal for keyword in keywords)]

    def _safe_arguments(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        goal: str,
    ) -> dict[str, Any]:
        normalized = dict(arguments)
        defaults: dict[str, dict[str, Any]] = {
            "search_course_knowledge": {"query": goal, "top_k": 10},
            "answer_course_question": {"question": goal, "top_k": 5},
            "generate_learning_path": {"goal": goal},
            "generate_explanation": {"topic": goal, "requirement": goal},
            "generate_quiz": {"topic": goal},
            "review_artifacts": {"content": goal},
        }
        for key, value in defaults.get(tool_name, {}).items():
            if not normalized.get(key):
                normalized[key] = value
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
            "你是智学工坊 Supervisor Agent。你必须根据用户目标、历史消息和工具观察动态决定下一步。"
            "优先调用有来源的知识检索工具；工具失败后调整方案，不要重复无效调用。"
            "任务完成时返回 JSON："
            '{"status":"complete","summary":"...","final_answer":"...","plan":[],"tool_calls":[]}.'
            "需要继续但不调用原生工具时返回 status=continue 和 tool_calls。"
            "不要输出隐式思维链，只输出简洁决策摘要。"
        )
        context = {
            "goal": state.get("goal"),
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
