# Review package: cfa441eb054a3f6da3edd9570cfc8ce0930540f5..HEAD

## Commits
fb9ca0f feat: limit agent tools by intent

## Files changed
 backend/app/agent_runtime/graph.py         |   7 +-
 backend/app/agent_runtime/tool_selector.py |  62 ++++++++++++++++
 backend/tests/test_agent_runtime.py        | 115 +++++++++++++++++++++++++++++
 3 files changed, 183 insertions(+), 1 deletion(-)

## Diff
diff --git a/backend/app/agent_runtime/graph.py b/backend/app/agent_runtime/graph.py
index 3b2c5ee..19c330d 100644
--- a/backend/app/agent_runtime/graph.py
+++ b/backend/app/agent_runtime/graph.py
@@ -3,20 +3,21 @@ from __future__ import annotations
 from typing import Any, Awaitable, Callable
 from uuid import UUID
 
 from langgraph.checkpoint.memory import InMemorySaver
 from langgraph.graph import END, START, StateGraph
 from langgraph.types import Command, interrupt
 
 from app.agent_runtime.answer_text import extract_final_answer_text
 from app.agent_runtime.state import AgentState
 from app.agent_runtime.supervisor import Supervisor
+from app.agent_runtime.tool_selector import select_tool_schemas
 from app.agent_runtime.tools import ToolContext, ToolRegistry
 from app.services.conversation_intent import is_simple_greeting
 
 
 StateHook = Callable[[AgentState], Awaitable[dict[str, Any]]]
 EventSink = Callable[[str, AgentState, dict[str, Any]], Awaitable[None]]
 
 
 class LearningAgentGraph:
     def __init__(
@@ -156,21 +157,23 @@ class LearningAgentGraph:
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
-        decision = await self.supervisor.decide(state, self.registry.tool_schemas())
+        tool_schemas = self.registry.tool_schemas()
+        candidate_tool_schemas = select_tool_schemas(state, tool_schemas)
+        decision = await self.supervisor.decide(state, candidate_tool_schemas)
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
@@ -180,20 +183,22 @@ class LearningAgentGraph:
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
+                "total_tool_count": len(tool_schemas),
+                "candidate_tool_count": len(candidate_tool_schemas),
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
diff --git a/backend/app/agent_runtime/tool_selector.py b/backend/app/agent_runtime/tool_selector.py
new file mode 100644
index 0000000..d695cc9
--- /dev/null
+++ b/backend/app/agent_runtime/tool_selector.py
@@ -0,0 +1,62 @@
+from __future__ import annotations
+
+from collections.abc import Mapping, Sequence
+from typing import Any
+
+from app.agent_runtime import supervisor_intents
+
+
+def select_tool_schemas(
+    state: Mapping[str, Any], tool_schemas: Sequence[dict[str, Any]]
+) -> list[dict[str, Any]]:
+    available = {str(item.get("function", {}).get("name")): item for item in tool_schemas}
+    goal = str(state.get("goal") or "")
+    planned = supervisor_intents.plan_required_tools(
+        goal,
+        is_profile_update_only=supervisor_intents.is_profile_update_only_goal(goal),
+    )
+    if not planned and _is_course_qa_goal(goal):
+        planned = ["search_course_knowledge", "answer_course_question"]
+    elif _requires_course_grounding(planned):
+        planned = ["search_course_knowledge", *planned]
+    names = _dedupe([*planned, *(state.get("tool_hints") or [])])
+    skipped = set(state.get("skip_tools") or [])
+    available_candidates = [name for name in names if name in available]
+    if available_candidates:
+        return [available[name] for name in available_candidates if name not in skipped]
+    return list(tool_schemas)
+
+
+def _dedupe(items: Sequence[str]) -> list[str]:
+    seen: set[str] = set()
+    ordered: list[str] = []
+    for item in items:
+        if item not in seen:
+            seen.add(item)
+            ordered.append(item)
+    return ordered
+
+
+def _requires_course_grounding(tool_names: Sequence[str]) -> bool:
+    return any(
+        name
+        in {
+            "answer_course_question",
+            "generate_explanation",
+            "generate_quiz",
+            "generate_mindmap",
+            "generate_diagram",
+            "generate_educational_image",
+            "generate_lesson_video",
+            "generate_immersive_classroom",
+            "generate_storyboard_html",
+            "generate_interactive_courseware",
+        }
+        for name in tool_names
+    )
+
+
+def _is_course_qa_goal(goal: str) -> bool:
+    return any(
+        keyword in goal for keyword in ("什么是", "讲解", "解释", "为什么", "如何", "帮我理解")
+    )
diff --git a/backend/tests/test_agent_runtime.py b/backend/tests/test_agent_runtime.py
index 641b154..3513ade 100644
--- a/backend/tests/test_agent_runtime.py
+++ b/backend/tests/test_agent_runtime.py
@@ -3,37 +3,152 @@ from __future__ import annotations
 from pathlib import Path
 from types import SimpleNamespace
 from uuid import uuid4
 
 import pytest
 
 from app.agent_runtime.graph import LearningAgentGraph
 from app.agent_runtime.service_tools import build_learning_tool_registry
 from app.agent_runtime.state import AgentDecision, PlannedToolCall
 from app.agent_runtime.supervisor import MiMoSupervisor
+from app.agent_runtime.tool_selector import select_tool_schemas
 from app.services.conversation_intent import is_simple_greeting
 from app.agent_runtime.tools import (
     AgentTool,
     ToolContext,
     ToolExecutionResult,
     ToolRegistry,
 )
 from app.llm.schemas import ChatResponse, ToolCall
 from app.models.agent_conversation import AgentConversation, AgentMessage, AgentTaskEvent
 from app.models.agent_task import AgentTask, AgentTaskStep
 from app.services.agent_queue_service import AgentEventBroker
 
 
 class QueryInput(SimpleNamespace):
     pass
 
 
+def schema(name: str) -> dict[str, object]:
+    return {
+        "type": "function",
+        "function": {"name": name, "parameters": {"type": "object"}},
+    }
+
+
+def test_course_qa_exposes_only_grounded_tools() -> None:
+    tools = [
+        schema(name)
+        for name in ("search_course_knowledge", "answer_course_question", "generate_quiz")
+    ]
+
+    selected = select_tool_schemas(
+        {"goal": "解释栈", "tool_hints": [], "skip_tools": []}, tools
+    )
+
+    assert [item["function"]["name"] for item in selected] == [  # type: ignore[index]
+        "search_course_knowledge",
+        "answer_course_question",
+    ]
+
+
+def test_ppt_excludes_video_tool() -> None:
+    tools = [
+        schema(name)
+        for name in (
+            "search_course_knowledge",
+            "generate_interactive_courseware",
+            "generate_lesson_video",
+        )
+    ]
+
+    selected = select_tool_schemas(
+        {"goal": "做一份二叉树 PPT", "tool_hints": [], "skip_tools": []}, tools
+    )
+
+    assert {item["function"]["name"] for item in selected} == {  # type: ignore[index]
+        "search_course_knowledge",
+        "generate_interactive_courseware",
+    }
+
+
+def test_skipping_every_candidate_does_not_expose_unrelated_tools() -> None:
+    tools = [
+        schema(name)
+        for name in ("search_course_knowledge", "answer_course_question", "generate_quiz")
+    ]
+
+    selected = select_tool_schemas(
+        {
+            "goal": "解释栈",
+            "tool_hints": [],
+            "skip_tools": ["search_course_knowledge", "answer_course_question"],
+        },
+        tools,
+    )
+
+    assert selected == []
+
+
+@pytest.mark.asyncio
+async def test_supervisor_receives_intent_scoped_schemas_and_plan_counts() -> None:
+    class InspectingSupervisor:
+        def __init__(self) -> None:
+            self.tool_names: list[str] = []
+
+        async def decide(self, state, tool_schemas):
+            self.tool_names = [item["function"]["name"] for item in tool_schemas]
+            return AgentDecision(
+                status="complete",
+                summary="回答完成",
+                final_answer="栈是后进先出。",
+            )
+
+    async def handler(context: ToolContext, arguments: dict[str, object]) -> ToolExecutionResult:
+        return ToolExecutionResult(output={"ok": True})
+
+    registry = ToolRegistry()
+    for name in ("search_course_knowledge", "answer_course_question", "generate_quiz"):
+        registry.register(
+            AgentTool(
+                name=name,
+                description=name,
+                agent_name="TestAgent",
+                input_schema={"type": "object", "properties": {}},
+                handler=handler,
+            )
+        )
+    events: list[tuple[str, dict[str, object]]] = []
+
+    async def event_sink(event_type, state, payload):
+        events.append((event_type, payload))
+
+    supervisor = InspectingSupervisor()
+    graph = LearningAgentGraph(registry=registry, supervisor=supervisor, event_sink=event_sink)
+    await graph._supervise(
+        {
+            "goal": "解释栈",
+            "tool_hints": [],
+            "skip_tools": [],
+            "iteration_count": 0,
+            "tool_call_count": 0,
+            "replan_count": 0,
+            "observations": [],
+        }
+    )
+
+    assert supervisor.tool_names == ["search_course_knowledge", "answer_course_question"]
+    plan_payload = next(payload for event_type, payload in events if event_type == "plan_created")
+    assert plan_payload["total_tool_count"] == 3
+    assert plan_payload["candidate_tool_count"] == 2
+
+
 def test_explicit_course_source_qa_plans_only_grounded_answer() -> None:
     from app.agent_runtime.supervisor_intents import plan_required_tools
 
     assert plan_required_tools(
         "基于课程资料解释栈并给出引用",
         is_profile_update_only=False,
     ) == ["answer_course_question"]
 
 
 def test_web_search_qa_does_not_fall_through_to_course_grounded_answer() -> None:
