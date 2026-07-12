from __future__ import annotations

import time
from typing import Any, Awaitable, Callable
from uuid import UUID

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.agent_runtime.answer_text import extract_final_answer_text
from app.agent_runtime.state import AgentState
from app.agent_runtime.supervisor import Supervisor
from app.agent_runtime.tool_selector import select_tool_schemas
from app.agent_runtime.tools import ToolContext, ToolRegistry
from app.services.conversation_intent import is_simple_greeting


StateHook = Callable[[AgentState], Awaitable[dict[str, Any]]]
EventSink = Callable[[str, AgentState, dict[str, Any]], Awaitable[None]]


class LearningAgentGraph:
    def __init__(
        self,
        *,
        registry: ToolRegistry,
        supervisor: Supervisor,
        checkpointer: object | None = None,
        context_loader: StateHook | None = None,
        reviewer: StateHook | None = None,
        memory_reflector: StateHook | None = None,
        event_sink: EventSink | None = None,
    ) -> None:
        self.registry = registry
        self.supervisor = supervisor
        self.context_loader = context_loader or self._empty_hook
        self.reviewer = reviewer or self._default_review
        self.memory_reflector = memory_reflector or self._empty_hook
        self.event_sink = event_sink or self._empty_event_sink
        builder = StateGraph(AgentState)
        builder.add_node("load_context", self._load_context)
        builder.add_node("supervisor", self._supervise)
        builder.add_node("execute_tool", self._execute_tool)
        builder.add_node("approval", self._approval)
        builder.add_node("observe", self._observe)
        builder.add_node("review", self._review)
        builder.add_node("memory_reflect", self._memory_reflect)
        builder.add_node("finalize", self._finalize)
        builder.add_edge(START, "load_context")
        builder.add_edge("load_context", "supervisor")
        builder.add_conditional_edges(
            "supervisor",
            self._route_supervisor,
            {
                "execute_tool": "execute_tool",
                "approval": "approval",
                "review": "review",
                "finalize": "finalize",
            },
        )
        builder.add_conditional_edges(
            "approval",
            self._route_approval,
            {"execute_tool": "execute_tool", "finalize": "finalize"},
        )
        builder.add_edge("execute_tool", "observe")
        builder.add_conditional_edges(
            "observe",
            self._route_observation,
            {"execute_tool": "execute_tool", "supervisor": "supervisor", "finalize": "finalize"},
        )
        builder.add_edge("review", "memory_reflect")
        builder.add_edge("memory_reflect", "finalize")
        builder.add_edge("finalize", END)
        self.graph = builder.compile(checkpointer=checkpointer or InMemorySaver())

    async def run(
        self,
        *,
        task_id: UUID,
        conversation_id: UUID,
        user_id: UUID,
        course_id: UUID,
        goal: str,
        thread_id: str,
        messages: list[dict[str, Any]] | None = None,
        max_iterations: int = 15,
        max_tool_calls: int = 30,
        max_replans: int = 5,
        tool_hints: list[str] | None = None,
        skip_tools: list[str] | None = None,
        tool_topics: dict[str, str] | None = None,
        parsed_intents: list[dict[str, Any]] | None = None,
    ) -> AgentState:
        initial: AgentState = {
            "task_id": str(task_id),
            "conversation_id": str(conversation_id),
            "thread_id": thread_id,
            "user_id": str(user_id),
            "course_id": str(course_id),
            "goal": goal,
            "messages": messages or [{"role": "user", "content": goal}],
            "context": {},
            "current_plan": [],
            "pending_tool_calls": [],
            "tool_calls": [],
            "observations": [],
            "artifacts": [],
            "citations": [],
            "iteration_count": 0,
            "tool_call_count": 0,
            "replan_count": 0,
            "max_iterations": max_iterations,
            "max_tool_calls": max_tool_calls,
            "max_replans": max_replans,
            "risk_level": "low",
            "status": "planning",
            "decision_summary": "",
            "final_answer": "",
            "error_message": "",
            "approved_tool_call_ids": [],
            "tool_hints": tool_hints or [],
            "skip_tools": skip_tools or [],
            "tool_topics": tool_topics or {},
            "parsed_intents": parsed_intents or [],
        }
        result = await self.graph.ainvoke(
            initial,
            config={"configurable": {"thread_id": thread_id}, "recursion_limit": 100},
            durability="sync",
        )
        if result.get("__interrupt__"):
            result["status"] = "waiting_confirmation"
        return result

    async def resume(self, *, thread_id: str, approved: bool) -> AgentState:
        result = await self.graph.ainvoke(
            Command(resume={"approved": approved}),
            config={"configurable": {"thread_id": thread_id}, "recursion_limit": 100},
            durability="sync",
        )
        if result.get("__interrupt__"):
            result["status"] = "waiting_confirmation"
        return result

    async def _load_context(self, state: AgentState) -> dict[str, Any]:
        await self.event_sink("planning", state, {"message": "加载会话、课程、画像与长期记忆"})
        loaded = await self.context_loader(state)
        return {"context": loaded, "status": "planning"}

    async def _supervise(self, state: AgentState) -> dict[str, Any]:
        iteration_count = state.get("iteration_count", 0) + 1
        if iteration_count > state.get("max_iterations", 15):
            return {
                "status": "failed",
                "error_message": "智能体超过最大规划/观察循环次数",
                "final_answer": self._budget_message(state),
                "iteration_count": iteration_count,
            }
        if state.get("tool_call_count", 0) >= state.get("max_tool_calls", 30):
            return {
                "status": "failed",
                "error_message": "智能体超过最大工具调用次数",
                "final_answer": self._budget_message(state),
                "iteration_count": iteration_count,
            }
        tool_schemas = self.registry.tool_schemas()
        candidate_tool_schemas = select_tool_schemas(state, tool_schemas)
        supervisor_started = time.perf_counter()
        decision = await self.supervisor.decide(state, candidate_tool_schemas)
        supervisor_duration_ms = int((time.perf_counter() - supervisor_started) * 1000)
        replans = state.get("replan_count", 0)
        observations = state.get("observations") or []
        if decision.status == "replan" or (observations and observations[-1].get("success") is False):
            replans += 1
        if replans > state.get("max_replans", 5):
            return {
                "status": "failed",
                "error_message": "智能体超过最大重新规划次数",
                "final_answer": self._budget_message(state),
                "iteration_count": iteration_count,
                "replan_count": replans,
            }
        event_type = "replanned" if replans > state.get("replan_count", 0) else "plan_created"
        await self.event_sink(
            event_type,
            state,
            {
                "summary": decision.summary,
                "plan": decision.plan,
                "tool_calls": [item.model_dump(mode="json") for item in decision.tool_calls],
                "reasoning_content": decision.reasoning_content or "",
                "iteration_count": iteration_count,
                "replan_count": replans,
                "total_tool_count": len(tool_schemas),
                "candidate_tool_count": len(candidate_tool_schemas),
                "supervisor_duration_ms": supervisor_duration_ms,
            },
        )
        return {
            "status": decision.status,
            "decision_summary": decision.summary,
            "current_plan": decision.plan,
            "pending_tool_calls": [item.model_dump(mode="json") for item in decision.tool_calls],
            "risk_level": decision.risk_level,
            "final_answer": decision.final_answer,
            "protocol_reasoning_content": decision.reasoning_content or "",
            "iteration_count": iteration_count,
            "replan_count": replans,
        }

    def _route_supervisor(self, state: AgentState) -> str:
        if state.get("status") in {"failed", "waiting_confirmation"}:
            return "finalize"
        if state.get("status") == "complete":
            if is_simple_greeting(str(state.get("goal") or "")) or self._is_fast_lookup_task(state):
                return "finalize"
            return "review"
        if state.get("pending_tool_calls"):
            call = state["pending_tool_calls"][0]
            if (
                self.registry.requires_confirmation(str(call["name"]))
                and str(call["id"]) not in (state.get("approved_tool_call_ids") or [])
            ):
                return "approval"
            return "execute_tool"
        return "review"

    async def _approval(self, state: AgentState) -> dict[str, Any]:
        call = state["pending_tool_calls"][0]
        await self.event_sink(
            "waiting_confirmation",
            state,
            {
                "tool_call_id": call["id"],
                "tool_name": call["name"],
                "arguments": call.get("arguments") or {},
                "risk_level": self.registry.risk_level(str(call["name"])),
            },
        )
        response = interrupt(
            {
                "tool_call_id": call["id"],
                "tool_name": call["name"],
                "arguments": call.get("arguments") or {},
                "risk_level": self.registry.risk_level(str(call["name"])),
                "message": f"工具 {call['name']} 需要用户确认后才能执行。",
            }
        )
        approved = bool(response.get("approved")) if isinstance(response, dict) else bool(response)
        if not approved:
            return {
                "status": "failed",
                "error_message": f"用户拒绝执行高风险工具 {call['name']}",
                "final_answer": "已停止执行需要确认的高风险操作。",
            }
        return {
            "status": "executing",
            "approved_tool_call_ids": [
                *(state.get("approved_tool_call_ids") or []),
                str(call["id"]),
            ],
        }

    def _route_approval(self, state: AgentState) -> str:
        return "finalize" if state.get("status") == "failed" else "execute_tool"

    async def _execute_tool(self, state: AgentState) -> dict[str, Any]:
        pending = list(state.get("pending_tool_calls") or [])
        call = pending.pop(0)
        name = str(call["name"])
        context = ToolContext(
            task_id=UUID(state["task_id"]),
            conversation_id=UUID(state["conversation_id"]),
            tool_call_id=str(call["id"]),
            user_id=UUID(state["user_id"]),
            course_id=UUID(state["course_id"]),
        )
        await self.event_sink(
            "tool_started",
            state,
            {
                "tool_call_id": call["id"],
                "tool_name": name,
                "arguments": call.get("arguments") or {},
            },
        )
        tool_started = time.perf_counter()
        result = await self.registry.execute(name, dict(call.get("arguments") or {}), context)
        duration_ms = int((time.perf_counter() - tool_started) * 1000)
        result.duration_ms = duration_ms
        await self.event_sink(
            "tool_completed",
            state,
            {
                "tool_call_id": call["id"],
                "tool_name": name,
                "success": result.success,
                "attempts": result.attempts,
                "duration_ms": duration_ms,
                "error_message": result.error_message,
                "artifact_refs": result.artifact_refs,
            },
        )
        return {
            "status": "executing",
            "pending_tool_calls": pending,
            "tool_call_count": state.get("tool_call_count", 0) + 1,
            "tool_calls": [
                *(state.get("tool_calls") or []),
                {
                    "id": call["id"],
                    "name": name,
                    "arguments": call.get("arguments") or {},
                    "success": result.success,
                    "attempts": result.attempts,
                },
            ],
            "last_tool_result": {
                "success": result.success,
                "tool_name": name,
                "tool_call_id": call["id"],
                "output": result.output,
                "evidence": result.evidence,
                "artifact_refs": result.artifact_refs,
                "citations": result.citations,
                "error_message": result.error_message,
                "final_answer": result.final_answer,
            },
        }

    async def _observe(self, state: AgentState) -> dict[str, Any]:
        result = dict(state.get("last_tool_result") or {})
        await self.event_sink("observation", state, result)
        update: dict[str, Any] = {
            "observations": [*(state.get("observations") or []), result],
            "artifacts": [
                *(state.get("artifacts") or []),
                *list(result.get("artifact_refs") or []),
            ],
            "citations": [
                *(state.get("citations") or []),
                *list(result.get("citations") or []),
            ],
            "status": "observing",
        }
        if result.get("success") and result.get("final_answer"):
            update["final_answer"] = result["final_answer"]
        return update

    def _route_observation(self, state: AgentState) -> str:
        result = state.get("last_tool_result", {})
        if state.get("pending_tool_calls") and result.get("success"):
            return "execute_tool"
        if result.get("success") and result.get("final_answer"):
            return "finalize"
        return "supervisor"

    async def _review(self, state: AgentState) -> dict[str, Any]:
        result = await self.reviewer(state)
        await self.event_sink("reviewed", state, result)
        return {"review_result": result, "status": "reviewed"}

    async def _memory_reflect(self, state: AgentState) -> dict[str, Any]:
        try:
            await self.memory_reflector(state)
        except Exception as exc:
            await self.event_sink(
                "memory_reflected",
                state,
                {
                    "message": "长期学习记忆反思未完成，已跳过并保留本次回答。",
                    "status": "skipped",
                    "error_message": str(exc)[:500],
                },
            )
            return {"status": "memory_reflected"}
        await self.event_sink("memory_reflected", state, {"message": "长期学习记忆反思完成", "status": "succeeded"})
        return {"status": "memory_reflected"}

    async def _finalize(self, state: AgentState) -> dict[str, Any]:
        status = state.get("status")
        if status not in {"failed", "waiting_confirmation"}:
            status = "completed"
        answer = extract_final_answer_text(state.get("final_answer") or "") or self._budget_message(state)
        event_type = "completed" if status == "completed" else status
        await self.event_sink(
            event_type,
            state,
            {
                "status": status,
                "final_answer": answer,
                "artifacts": state.get("artifacts") or [],
                "citations": state.get("citations") or [],
            },
        )
        return {"status": status, "final_answer": answer}

    async def _empty_hook(self, state: AgentState) -> dict[str, Any]:
        return {}

    async def _empty_event_sink(
        self,
        event_type: str,
        state: AgentState,
        payload: dict[str, Any],
    ) -> None:
        return None

    async def _default_review(self, state: AgentState) -> dict[str, Any]:
        return {
            "passed": True,
            "citation_count": len(state.get("citations") or []),
            "artifact_count": len(state.get("artifacts") or []),
        }

    def _budget_message(self, state: AgentState) -> str:
        completed = len(state.get("artifacts") or [])
        return f"智能体已停止继续执行，当前已生成 {completed} 个产物。请查看执行记录后继续。"

    @staticmethod
    def _is_fast_lookup_task(state: AgentState) -> bool:
        """纯检索/联网搜索任务跳过 Review 与长期记忆，加快返回最终回答。"""
        completed = {
            str(item.get("tool_name"))
            for item in state.get("observations") or []
            if item.get("success") is True and item.get("tool_name")
        }
        if not completed:
            return False
        lookup_tools = {"search_web", "search_course_knowledge", "answer_course_question"}
        return completed.issubset(lookup_tools)
