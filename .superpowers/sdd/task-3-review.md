# Review package: 5b8a280d1cd3d6ac925f19d033a6c5f0e60b8bb7..HEAD

## Commits
47128a8 refactor: separate supervisor responsibilities

## Files changed
 backend/app/agent_runtime/graph.py                 |   4 +
 backend/app/agent_runtime/supervisor.py            | 150 ++++-----------------
 backend/app/agent_runtime/supervisor_completion.py | 129 ++++++++++++++++++
 backend/app/agent_runtime/supervisor_policy.py     | 104 ++++++++++++++
 backend/app/agent_runtime/supervisor_prompt.py     |  66 +++++++++
 backend/tests/test_agent_runtime.py                |   2 +
 backend/tests/test_supervisor_intents.py           |   7 +
 7 files changed, 335 insertions(+), 127 deletions(-)

## Diff
diff --git a/backend/app/agent_runtime/graph.py b/backend/app/agent_runtime/graph.py
index 19c330d..34cb104 100644
--- a/backend/app/agent_runtime/graph.py
+++ b/backend/app/agent_runtime/graph.py
@@ -1,12 +1,13 @@
 from __future__ import annotations
 
+import time
 from typing import Any, Awaitable, Callable
 from uuid import UUID
 
 from langgraph.checkpoint.memory import InMemorySaver
 from langgraph.graph import END, START, StateGraph
 from langgraph.types import Command, interrupt
 
 from app.agent_runtime.answer_text import extract_final_answer_text
 from app.agent_runtime.state import AgentState
 from app.agent_runtime.supervisor import Supervisor
@@ -159,21 +160,23 @@ class LearningAgentGraph:
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
+        supervisor_started = time.perf_counter()
         decision = await self.supervisor.decide(state, candidate_tool_schemas)
+        supervisor_duration_ms = int((time.perf_counter() - supervisor_started) * 1000)
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
@@ -185,20 +188,21 @@ class LearningAgentGraph:
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
+                "supervisor_duration_ms": supervisor_duration_ms,
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
diff --git a/backend/app/agent_runtime/supervisor.py b/backend/app/agent_runtime/supervisor.py
index a072aa8..3766c60 100644
--- a/backend/app/agent_runtime/supervisor.py
+++ b/backend/app/agent_runtime/supervisor.py
@@ -1,19 +1,27 @@
 from __future__ import annotations
 
 import json
 from typing import Any, Protocol
 from uuid import uuid4
 
 from pydantic import ValidationError
 
 from app.agent_runtime.answer_text import extract_final_answer_text
+from app.agent_runtime.supervisor_completion import (
+    build_completion_answer,
+    build_search_results_answer,
+    format_search_output_answer,
+    normalize_completion_answer,
+)
+from app.agent_runtime.supervisor_policy import apply_safety_net
+from app.agent_runtime.supervisor_prompt import build_messages
 from app.agent_runtime.state import AgentDecision, PlannedToolCall
 from app.agent_runtime import supervisor_intents
 from app.llm.schemas import ChatMessage, ToolCall
 from app.services.conversation_intent import is_simple_greeting, simple_greeting_answer
 
 
 class Supervisor(Protocol):
     async def decide(
         self,
         state: dict[str, Any],
@@ -132,20 +140,28 @@ class MiMoSupervisor:
             status="failed",
             summary="Supervisor 未返回可执行决策。",
             final_answer="智能体未能生成有效计划，请补充目标后重试。",
         )
 
     def _apply_safety_net(
         self,
         state: dict[str, Any],
         tool_schemas: list[dict[str, Any]],
         decision: AgentDecision,
+    ) -> AgentDecision:
+        return apply_safety_net(self, state, tool_schemas, decision)
+
+    def _apply_safety_net_legacy(
+        self,
+        state: dict[str, Any],
+        tool_schemas: list[dict[str, Any]],
+        decision: AgentDecision,
     ) -> AgentDecision:
         """LLM 决策优先；仅在交付物缺失、显式约束或 LLM 空转时介入。"""
         goal = str(state.get("goal") or "")
         available = self._available_tool_names(tool_schemas)
         completed_tools = self._completed_tool_names(state)
         skip_tools = set(state.get("skip_tools") or [])
 
         observations = list(state.get("observations") or [])
         if observations and observations[-1].get("success") is False:
             err = str(observations[-1].get("error_message") or "工具执行失败")
@@ -528,112 +544,28 @@ class MiMoSupervisor:
         pending = self._pending_deliverables(goal, available, completed_tools, skip_tools)
         if pending:
             return None
         return AgentDecision(
             status="complete",
             summary="所需交付物已全部生成。",
             final_answer=self._build_completion_answer(state),
         )
 
     def _build_completion_answer(self, state: dict[str, Any]) -> str:
-        goal = str(state.get("goal") or "")
-        search_answer = self._build_search_results_answer(state, goal)
-        if search_answer:
-            return search_answer
-
-        artifacts = state.get("artifacts") or []
-        lines = ["所需学习内容已生成，请查看下方产物卡片或资源侧栏。"]
-        for artifact in artifacts:
-            if not isinstance(artifact, dict):
-                continue
-            title = str(artifact.get("title") or artifact.get("name") or "学习产物")
-            subtype = str(artifact.get("subtype") or artifact.get("asset_type") or artifact.get("type") or "")
-            if subtype == "image" or artifact.get("mime_type", "").startswith("image/"):
-                lines.append(f"- 教学插图：{title}")
-            elif subtype in {"mindmap", "diagram"} or artifact.get("type") == "resource":
-                lines.append(f"- 知识卡片/资源：{title}")
-            elif artifact.get("type") == "quiz":
-                lines.append(f"- 练习题：{title}")
-            elif artifact.get("type") == "learning_path":
-                lines.append(f"- 学习路径：{title}")
-            elif artifact.get("type") == "media_asset":
-                lines.append(f"- 多模态产物：{title}")
-        if len(lines) == 1 and state.get("observations"):
-            lines.append("- 相关工具已执行完成，可在执行详情中查看输出。")
-        return "\n".join(lines)
+        return build_completion_answer(state)
 
     def _build_search_results_answer(self, state: dict[str, Any], goal: str) -> str | None:
-        observations = list(state.get("observations") or [])
-        for obs in reversed(observations):
-            if obs.get("success") is not True:
-                continue
-            tool_name = str(obs.get("tool_name") or "")
-            if tool_name != "answer_course_question":
-                continue
-            output = obs.get("output")
-            if not isinstance(output, dict):
-                continue
-            for key in ("answer", "content", "summary"):
-                value = output.get(key)
-                if isinstance(value, str) and value.strip():
-                    return value.strip()
-
-        for obs in reversed(observations):
-            if obs.get("success") is not True:
-                continue
-            tool_name = str(obs.get("tool_name") or "")
-            if tool_name not in {"search_web", "search_course_knowledge"}:
-                continue
-            output = obs.get("output")
-            if not isinstance(output, dict):
-                continue
-            return self._format_search_output_answer(tool_name, output, goal)
-        return None
+        return build_search_results_answer(state, goal)
 
     @staticmethod
     def _format_search_output_answer(tool_name: str, output: dict[str, Any], goal: str) -> str:
-        query = str(output.get("query") or goal).strip()
-        items = output.get("items") or []
-        lines: list[str] = []
-        if tool_name == "search_web":
-            lines.append(f"## 联网搜索：{query}\n")
-            message = str(output.get("message") or "").strip()
-            if message and output.get("provider") == "mock":
-                lines.append(f"_{message}_\n")
-        else:
-            lines.append(f"## 课程资料检索：{query}\n")
-
-        if not items:
-            lines.append("未找到相关结果，请尝试换关键词或补充更具体的描述。")
-            return "\n".join(lines).strip()
-
-        lines.append("为你找到以下参考来源：\n")
-        for index, item in enumerate(items[:5], start=1):
-            if not isinstance(item, dict):
-                continue
-            title = str(item.get("title") or f"结果 {index}")
-            url = str(item.get("url") or "").strip()
-            snippet = str(item.get("snippet") or item.get("content") or "").strip()
-            if len(snippet) > 400:
-                snippet = snippet[:400].rstrip() + "…"
-            lines.append(f"{index}. **{title}**")
-            if snippet:
-                lines.append(f"   {snippet}")
-            if url:
-                lines.append(f"   来源：{url}")
-            lines.append("")
-
-        if tool_name == "search_web":
-            lines.append("> 以上信息来自互联网公开资料，建议结合官方文档进一步核实。")
-        else:
-            lines.append("> 以上内容来自你的课程资料检索结果。")
-        return "\n".join(lines).strip()
+        return format_search_output_answer(tool_name, output, goal)
 
     def _profile_update_only_decision(
         self,
         state: dict[str, Any],
         tool_schemas: list[dict[str, Any]],
     ) -> AgentDecision | None:
         goal = str(state.get("goal") or "")
         if not self._is_profile_update_only_goal(goal):
             return None
         available = {
@@ -726,60 +658,21 @@ class MiMoSupervisor:
             "synthesize_speech",
         }
         return bool(completed & generation)
 
     def _normalize_completion_answer(
         self,
         state: dict[str, Any],
         goal: str,
         answer: str,
     ) -> str:
-        observations = list(state.get("observations") or [])
-        for obs in reversed(observations):
-            if obs.get("success") is not True:
-                continue
-            tool_name = str(obs.get("tool_name") or "")
-            output = obs.get("output") if isinstance(obs.get("output"), dict) else {}
-            if tool_name == "generate_interactive_courseware":
-                title = str(output.get("title") or "互动课件")
-                asset_id = output.get("asset_id") or output.get("media_asset_id")
-                return (
-                    f"互动课件已生成：{title}\n"
-                    f"- 请在下方产物卡片或资源侧栏打开 HTML 课件预览"
-                    + (f"\n- asset_id={asset_id}" if asset_id else "")
-                )
-            if tool_name == "generate_lesson_video":
-                job_id = output.get("media_job_id") or output.get("job_id")
-                return (
-                    "讲解视频任务已提交后台队列，尚未完成渲染。\n"
-                    f"- job_id={job_id}\n"
-                    "- 请在执行轨迹查看进度；若出现 failed 步骤，说明后台渲染失败，需要重试或改选互动课件。"
-                )
-            if tool_name == "generate_immersive_classroom":
-                job_id = output.get("media_job_id") or output.get("job_id")
-                return (
-                    "沉浸课堂任务已提交后台队列。\n"
-                    f"- job_id={job_id}\n"
-                    "- 请在执行轨迹查看 OpenMAIC 生成进度。"
-                )
-            if tool_name in {"search_web", "search_course_knowledge"}:
-                formatted = self._format_search_output_answer(tool_name, output, goal)
-                if formatted:
-                    return formatted
-        search_answer = self._build_search_results_answer(state, goal)
-        if search_answer:
-            return search_answer
-        if supervisor_intents.presentation_intent(goal) and answer:
-            if "视频" in answer and "课件" not in answer:
-                return self._build_completion_answer(state)
-        cleaned = extract_final_answer_text(answer)
-        return cleaned or self._build_completion_answer(state)
+        return normalize_completion_answer(state, goal, answer)
 
     def _is_profile_update_only_goal(self, goal: str) -> bool:
         return supervisor_intents.is_profile_update_only_goal(goal)
 
     def _required_tools(self, goal: str) -> list[str]:
         tools = supervisor_intents.plan_required_tools(
             goal,
             is_profile_update_only=self._is_profile_update_only_goal(goal),
         )
         return self._ensure_knowledge_search_first(goal, tools)
@@ -996,20 +889,23 @@ class MiMoSupervisor:
                         item.get("arguments") or item.get("parameters") or item.get("args") or {}
                     ),
                 }
             )
         normalized["tool_calls"] = calls
         if not normalized.get("plan") and normalized.get("summary"):
             normalized["plan"] = [str(normalized["summary"])]
         return normalized
 
     def _build_messages(self, state: dict[str, Any]) -> list[ChatMessage]:
+        return build_messages(state)
+
+    def _build_messages_legacy(self, state: dict[str, Any]) -> list[ChatMessage]:
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
diff --git a/backend/app/agent_runtime/supervisor_completion.py b/backend/app/agent_runtime/supervisor_completion.py
new file mode 100644
index 0000000..dc02dca
--- /dev/null
+++ b/backend/app/agent_runtime/supervisor_completion.py
@@ -0,0 +1,129 @@
+from __future__ import annotations
+
+from typing import Any
+
+from app.agent_runtime.answer_text import extract_final_answer_text
+from app.agent_runtime import supervisor_intents
+
+
+def format_search_output_answer(tool_name: str, output: dict[str, Any], goal: str) -> str:
+    query = str(output.get("query") or goal).strip()
+    items = output.get("items") or []
+    lines: list[str] = []
+    if tool_name == "search_web":
+        lines.append(f"## 联网搜索：{query}\n")
+        message = str(output.get("message") or "").strip()
+        if message and output.get("provider") == "mock":
+            lines.append(f"_{message}_\n")
+    else:
+        lines.append(f"## 课程资料检索：{query}\n")
+
+    if not items:
+        lines.append("未找到相关结果，请尝试换关键词或补充更具体的描述。")
+        return "\n".join(lines).strip()
+
+    lines.append("为你找到以下参考来源：\n")
+    for index, item in enumerate(items[:5], start=1):
+        if not isinstance(item, dict):
+            continue
+        title = str(item.get("title") or f"结果 {index}")
+        url = str(item.get("url") or "").strip()
+        snippet = str(item.get("snippet") or item.get("content") or "").strip()
+        if len(snippet) > 400:
+            snippet = snippet[:400].rstrip() + "…"
+        lines.append(f"{index}. **{title}**")
+        if snippet:
+            lines.append(f"   {snippet}")
+        if url:
+            lines.append(f"   来源：{url}")
+        lines.append("")
+
+    if tool_name == "search_web":
+        lines.append("> 以上信息来自互联网公开资料，建议结合官方文档进一步核实。")
+    else:
+        lines.append("> 以上内容来自你的课程资料检索结果。")
+    return "\n".join(lines).strip()
+
+
+def build_search_results_answer(state: dict[str, Any], goal: str) -> str | None:
+    observations = list(state.get("observations") or [])
+    for obs in reversed(observations):
+        if obs.get("success") is not True or str(obs.get("tool_name") or "") != "answer_course_question":
+            continue
+        output = obs.get("output")
+        if not isinstance(output, dict):
+            continue
+        for key in ("answer", "content", "summary"):
+            value = output.get(key)
+            if isinstance(value, str) and value.strip():
+                return value.strip()
+
+    for obs in reversed(observations):
+        if obs.get("success") is not True:
+            continue
+        tool_name = str(obs.get("tool_name") or "")
+        if tool_name not in {"search_web", "search_course_knowledge"}:
+            continue
+        output = obs.get("output")
+        if isinstance(output, dict):
+            return format_search_output_answer(tool_name, output, goal)
+    return None
+
+
+def build_completion_answer(state: dict[str, Any]) -> str:
+    search_answer = build_search_results_answer(state, str(state.get("goal") or ""))
+    if search_answer:
+        return search_answer
+
+    lines = ["所需学习内容已生成，请查看下方产物卡片或资源侧栏。"]
+    for artifact in state.get("artifacts") or []:
+        if not isinstance(artifact, dict):
+            continue
+        title = str(artifact.get("title") or artifact.get("name") or "学习产物")
+        subtype = str(artifact.get("subtype") or artifact.get("asset_type") or artifact.get("type") or "")
+        if subtype == "image" or str(artifact.get("mime_type") or "").startswith("image/"):
+            lines.append(f"- 教学插图：{title}")
+        elif subtype in {"mindmap", "diagram"} or artifact.get("type") == "resource":
+            lines.append(f"- 知识卡片/资源：{title}")
+        elif artifact.get("type") == "quiz":
+            lines.append(f"- 练习题：{title}")
+        elif artifact.get("type") == "learning_path":
+            lines.append(f"- 学习路径：{title}")
+        elif artifact.get("type") == "media_asset":
+            lines.append(f"- 多模态产物：{title}")
+    if len(lines) == 1 and state.get("observations"):
+        lines.append("- 相关工具已执行完成，可在执行详情中查看输出。")
+    return "\n".join(lines)
+
+
+def normalize_completion_answer(state: dict[str, Any], goal: str, answer: str) -> str:
+    for obs in reversed(state.get("observations") or []):
+        if obs.get("success") is not True:
+            continue
+        tool_name = str(obs.get("tool_name") or "")
+        output = obs.get("output") if isinstance(obs.get("output"), dict) else {}
+        if tool_name == "generate_interactive_courseware":
+            title = str(output.get("title") or "互动课件")
+            asset_id = output.get("asset_id") or output.get("media_asset_id")
+            return (
+                f"互动课件已生成：{title}\n- 请在下方产物卡片或资源侧栏打开 HTML 课件预览"
+                + (f"\n- asset_id={asset_id}" if asset_id else "")
+            )
+        if tool_name == "generate_lesson_video":
+            job_id = output.get("media_job_id") or output.get("job_id")
+            return (
+                "讲解视频任务已提交后台队列，尚未完成渲染。\n"
+                f"- job_id={job_id}\n"
+                "- 请在执行轨迹查看进度；若出现 failed 步骤，说明后台渲染失败，需要重试或改选互动课件。"
+            )
+        if tool_name == "generate_immersive_classroom":
+            job_id = output.get("media_job_id") or output.get("job_id")
+            return f"沉浸课堂任务已提交后台队列。\n- job_id={job_id}\n- 请在执行轨迹查看 OpenMAIC 生成进度。"
+        if tool_name in {"search_web", "search_course_knowledge"}:
+            return format_search_output_answer(tool_name, output, goal)
+    search_answer = build_search_results_answer(state, goal)
+    if search_answer:
+        return search_answer
+    if supervisor_intents.presentation_intent(goal) and answer and "视频" in answer and "课件" not in answer:
+        return build_completion_answer(state)
+    return extract_final_answer_text(answer) or build_completion_answer(state)
diff --git a/backend/app/agent_runtime/supervisor_policy.py b/backend/app/agent_runtime/supervisor_policy.py
new file mode 100644
index 0000000..70f7d34
--- /dev/null
+++ b/backend/app/agent_runtime/supervisor_policy.py
@@ -0,0 +1,104 @@
+from __future__ import annotations
+
+from typing import Any, Protocol
+
+from app.agent_runtime import supervisor_intents
+from app.agent_runtime.state import AgentDecision
+
+
+class _PolicyHost(Protocol):
+    def _available_tool_names(self, tool_schemas: list[dict[str, Any]]) -> set[str]: ...
+    def _completed_tool_names(self, state: dict[str, Any]) -> set[str]: ...
+    def _is_profile_update_only_goal(self, goal: str) -> bool: ...
+    def _force_tool(self, tool_name: str, goal: str, state: dict[str, Any], decision: AgentDecision, *, reason: str) -> AgentDecision: ...
+    def _pending_deliverables(self, goal: str, available: set[str], completed_tools: set[str], skip_tools: set[str]) -> list[str]: ...
+    def _filter_tool_calls_for_profile_only(self, goal: str, tool_calls: list[Any]) -> list[Any]: ...
+    def _align_tool_calls_with_deliverables(self, goal: str, completed_tools: set[str], tool_calls: list[Any], available: set[str], skip_tools: set[str], state: dict[str, Any]) -> list[Any]: ...
+    def _safe_arguments(self, tool_name: str, arguments: dict[str, Any], goal: str, state: dict[str, Any] | None = None) -> dict[str, Any]: ...
+    def _next_tool_hint(self, state: dict[str, Any], available: set[str], completed_tools: set[str], skip_tools: set[str]) -> str | None: ...
+    def _requires_explicit_retrieval(self, goal: str, completed_tools: set[str], state: dict[str, Any], skip_tools: set[str]) -> bool: ...
+    def _has_wrong_deliverable_only(self, state: dict[str, Any], goal: str) -> bool: ...
+    def _normalize_completion_answer(self, state: dict[str, Any], goal: str, answer: str) -> str: ...
+    def _should_use_fallback_planner(self, goal: str, state: dict[str, Any], available: set[str], completed_tools: set[str], skip_tools: set[str], pending_deliverables: list[str]) -> bool: ...
+    def _fallback_next_tool(self, goal: str, available: set[str], completed_tools: set[str], skip_tools: set[str]) -> str | None: ...
+    def _build_completion_answer(self, state: dict[str, Any]) -> str: ...
+
+
+def apply_safety_net(
+    host: _PolicyHost,
+    state: dict[str, Any],
+    tool_schemas: list[dict[str, Any]],
+    decision: AgentDecision,
+) -> AgentDecision:
+    """Apply the deterministic safety boundary around an LLM decision."""
+    goal = str(state.get("goal") or "")
+    available = host._available_tool_names(tool_schemas)
+    completed_tools = host._completed_tool_names(state)
+    skip_tools = set(state.get("skip_tools") or [])
+    observations = list(state.get("observations") or [])
+    if observations and observations[-1].get("success") is False:
+        err = str(observations[-1].get("error_message") or "工具执行失败")
+        return AgentDecision(
+            status="failed",
+            summary="工具执行失败，已停止本轮任务。",
+            final_answer=(
+                f"生成未成功：{err}\n\n"
+                "请查看上方执行轨迹中的失败步骤；若是视频渲染报错，可改选「互动课件/PPT」或稍后重试。"
+            ),
+            reasoning_content=decision.reasoning_content,
+        )
+
+    required_tools = supervisor_intents.plan_required_tools(
+        goal, is_profile_update_only=host._is_profile_update_only_goal(goal)
+    )
+    if required_tools == ["answer_course_question"] and "answer_course_question" in available and "answer_course_question" not in completed_tools and "answer_course_question" not in skip_tools:
+        return host._force_tool("answer_course_question", goal, state, decision, reason="显式课程依据问答统一由可信问答内核完成")
+
+    if decision.tool_calls:
+        if decision.status == "complete":
+            decision.status = "continue"
+        decision.tool_calls = [
+            call for call in decision.tool_calls
+            if call.name not in completed_tools and call.name not in skip_tools
+        ]
+        if not decision.tool_calls:
+            pending = host._pending_deliverables(goal, available, completed_tools, skip_tools)
+            if not pending:
+                return AgentDecision(status="complete", summary="所需交付物已全部生成。", final_answer=host._build_completion_answer(state), reasoning_content=decision.reasoning_content)
+            tool_name = pending[0]
+            return host._force_tool(tool_name, goal, state, decision, reason=f"用户要求的{supervisor_intents.deliverable_label(tool_name)}尚未生成，禁止重复调用已完成工具")
+        decision.tool_calls = host._filter_tool_calls_for_profile_only(goal, decision.tool_calls)
+        decision.tool_calls = host._align_tool_calls_with_deliverables(goal, completed_tools, decision.tool_calls, available, skip_tools, state)
+        for call in decision.tool_calls:
+            call.arguments = host._safe_arguments(call.name, call.arguments, goal, state)
+        if decision.tool_calls:
+            return decision
+        pending = host._pending_deliverables(goal, available, completed_tools, skip_tools)
+        if pending:
+            tool_name = pending[0]
+            return host._force_tool(tool_name, goal, state, decision, reason=f"用户要求的{supervisor_intents.deliverable_label(tool_name)}尚未生成，安全约束后需补调")
+
+    pending = host._pending_deliverables(goal, available, completed_tools, skip_tools)
+    hint = host._next_tool_hint(state, available, completed_tools, skip_tools)
+    if hint and decision.status == "complete":
+        return host._force_tool(hint, goal, state, decision, reason="用户指定工具")
+    if decision.status == "complete" and host._requires_explicit_retrieval(goal, completed_tools, state, skip_tools) and (("answer_course_question" in available and "answer_course_question" not in skip_tools) or ("search_course_knowledge" in available and "search_course_knowledge" not in skip_tools)):
+        grounded_tool = "answer_course_question" if required_tools == ["answer_course_question"] and "answer_course_question" in available and "answer_course_question" not in skip_tools else "search_course_knowledge"
+        return host._force_tool(grounded_tool, goal, state, decision, reason="用户明确要求基于课程资料回答，必须使用可信问答内核" if grounded_tool == "answer_course_question" else "生成多模态产物前必须先检索课程依据")
+    if decision.status == "complete" and supervisor_intents.web_search_intent(goal) and "search_web" not in completed_tools and "search_web" in available and "search_web" not in skip_tools:
+        return host._force_tool("search_web", goal, state, decision, reason="用户要求联网搜索，必须先获取实时网页结果")
+    if decision.status == "complete" and pending:
+        tool_name = pending[0]
+        return host._force_tool(tool_name, goal, state, decision, reason=f"用户要求的{supervisor_intents.deliverable_label(tool_name)}尚未生成，禁止仅用文字/Markdown 代替")
+    if decision.status == "complete" and host._has_wrong_deliverable_only(state, goal):
+        wrong_pending = host._pending_deliverables(goal, available, completed_tools, skip_tools)
+        if wrong_pending:
+            tool_name = wrong_pending[0]
+            return host._force_tool(tool_name, goal, state, decision, reason=f"已调用错误工具，需补生成{supervisor_intents.deliverable_label(tool_name)}")
+    if decision.status == "complete":
+        decision.final_answer = host._normalize_completion_answer(state, goal, decision.final_answer)
+    if decision.status == "complete" and host._should_use_fallback_planner(goal, state, available, completed_tools, skip_tools, pending):
+        fallback = host._fallback_next_tool(goal, available, completed_tools, skip_tools)
+        if fallback:
+            return host._force_tool(fallback, goal, state, decision, reason=f"LLM 未调用工具，安全网补调 {fallback}")
+    return decision
diff --git a/backend/app/agent_runtime/supervisor_prompt.py b/backend/app/agent_runtime/supervisor_prompt.py
new file mode 100644
index 0000000..5c46175
--- /dev/null
+++ b/backend/app/agent_runtime/supervisor_prompt.py
@@ -0,0 +1,66 @@
+from __future__ import annotations
+
+import json
+from typing import Any
+
+from app.agent_runtime import supervisor_intents
+from app.llm.schemas import ChatMessage, ToolCall
+
+
+def build_messages(state: dict[str, Any]) -> list[ChatMessage]:
+    system = (
+        "你是智学工坊 Supervisor Agent。你的职责是根据用户目标、历史消息和工具观察，"
+        "**直接通过原生 function calling 选择下一步工具**。"
+        "优先调用有来源的知识检索工具；工具失败后调整方案，不要重复无效调用。"
+        "交付物必须与用户意图一致：语音→synthesize_speech，普通短视频→generate_lesson_video，"
+        "沉浸课堂/一键课程→generate_immersive_classroom，"
+        "PPT/幻灯片/课件/slides/deck/keynote/网页ppt→generate_interactive_courseware（多页 HTML 互动课件，不是视频），"
+        "插图→generate_educational_image，流程图→generate_diagram，思维导图→generate_mindmap，练习→generate_quiz，"
+        "纯答疑→answer_course_question，文字讲解资源→generate_explanation。"
+        "用户一句话包含多个交付物（如「二叉树 ppt 和队列思维导图」）时，必须分别调用对应工具，"
+        "每个工具的 topic/concept 只用该子任务的主题词，不要把整句当 topic。"
+        "用户说「讲解 ppt / 做一份幻灯片 / 课件」时，禁止调用 generate_lesson_video。"
+        "禁止把文字资源、Markdown 或摘要冒充语音/视频/图片结果。"
+        "当用户要求语音时，先准备讲解文本（检索/生成），再 synthesize_speech。"
+        "当用户要求插图/知识卡片时：有文生图 API 则 generate_educational_image；"
+        "无 API 时同一工具会自动产出简明 Mermaid 知识卡片（思维导图或流程图）。"
+        "Mermaid 与文生图均应保持节点/元素简明，复杂知识用多层而非单节点堆字。"
+        "只有在任务真正完成、且不需要再调用工具时，才返回纯文本 final_answer。"
+        "若仍需工具，请直接发起 tool call，不要只返回 JSON 计划。"
+        "不要输出隐式思维链，只输出简洁决策摘要。"
+    )
+    goal = str(state.get("goal") or "")
+    profile_only = supervisor_intents.is_profile_update_only_goal(goal)
+    recommended = supervisor_intents.plan_required_tools(goal, is_profile_update_only=profile_only)
+    context = {
+        "goal": state.get("goal"),
+        "recommended_tools": recommended,
+        "recommended_tool_labels": [supervisor_intents.deliverable_label(name) for name in recommended],
+        "tool_topics": state.get("tool_topics") or supervisor_intents.parse_tool_topics(goal),
+        "parsed_intents": state.get("parsed_intents") or [
+            {"segment": item.segment, "topic": item.topic, "tools": list(item.tools)}
+            for item in supervisor_intents.parse_goal_intents(goal)
+        ],
+        "current_plan": state.get("current_plan") or [],
+        "observations": (state.get("observations") or [])[-8:],
+        "artifacts": state.get("artifacts") or [],
+        "learning_context": state.get("context") or {},
+        "iteration_count": state.get("iteration_count") or 0,
+    }
+    messages = [ChatMessage(role="system", content=system)]
+    messages.extend(
+        ChatMessage(role=str(item.get("role") or "user"), content=str(item.get("content") or ""))
+        for item in (state.get("messages") or [])[-12:]
+    )
+    prior_tool_calls = state.get("tool_calls") or []
+    observations = state.get("observations") or []
+    reasoning_content = state.get("protocol_reasoning_content")
+    if reasoning_content and prior_tool_calls and observations:
+        last_call = prior_tool_calls[-1]
+        messages.append(ChatMessage(
+            role="assistant", content="", reasoning_content=str(reasoning_content),
+            tool_calls=[ToolCall(id=str(last_call.get("id") or ""), name=str(last_call.get("name") or ""), arguments=dict(last_call.get("arguments") or {}))],
+        ))
+        messages.append(ChatMessage(role="tool", tool_call_id=str(last_call.get("id") or ""), content=json.dumps(observations[-1], ensure_ascii=False)))
+    messages.append(ChatMessage(role="user", content=f"当前任务状态：{json.dumps(context, ensure_ascii=False)}"))
+    return messages
diff --git a/backend/tests/test_agent_runtime.py b/backend/tests/test_agent_runtime.py
index 217d3a6..1eb20c1 100644
--- a/backend/tests/test_agent_runtime.py
+++ b/backend/tests/test_agent_runtime.py
@@ -207,20 +207,22 @@ async def test_supervisor_receives_intent_scoped_schemas_and_plan_counts() -> No
             "tool_call_count": 0,
             "replan_count": 0,
             "observations": [],
         }
     )
 
     assert supervisor.tool_names == ["search_course_knowledge", "answer_course_question"]
     plan_payload = next(payload for event_type, payload in events if event_type == "plan_created")
     assert plan_payload["total_tool_count"] == 3
     assert plan_payload["candidate_tool_count"] == 2
+    assert isinstance(plan_payload["supervisor_duration_ms"], int)
+    assert plan_payload["supervisor_duration_ms"] >= 0
 
 
 def test_explicit_course_source_qa_plans_only_grounded_answer() -> None:
     from app.agent_runtime.supervisor_intents import plan_required_tools
 
     assert plan_required_tools(
         "基于课程资料解释栈并给出引用",
         is_profile_update_only=False,
     ) == ["answer_course_question"]
 
diff --git a/backend/tests/test_supervisor_intents.py b/backend/tests/test_supervisor_intents.py
index 0d4e0d5..95225f5 100644
--- a/backend/tests/test_supervisor_intents.py
+++ b/backend/tests/test_supervisor_intents.py
@@ -1,28 +1,35 @@
 """Supervisor 意图路由回归测试 — 防止工具误匹配。"""
 
 from __future__ import annotations
 
 import pytest
 
 from app.agent_runtime import supervisor_intents
+from app.agent_runtime.supervisor_completion import format_search_output_answer
 from app.agent_runtime.supervisor import MiMoSupervisor
 from app.llm.schemas import ChatResponse, ToolCall
 
 
 class DirectCompleteProvider:
     async def chat(self, messages, **kwargs):
         return ChatResponse(
             content='{"status":"complete","summary":"直接完成","final_answer":"这是文字回答。"}'
         )
 
 
+def test_completion_formats_empty_course_search() -> None:
+    answer = format_search_output_answer("search_course_knowledge", {"items": []}, "栈")
+
+    assert "未找到相关结果" in answer
+
+
 @pytest.mark.parametrize(
     ("goal", "must_include", "must_exclude"),
     [
         ("生成讲解队列的语音", ["generate_explanation", "synthesize_speech"], []),
         ("生成队列讲解视频", ["generate_lesson_video"], ["synthesize_speech"]),
         ("为 BFS 生成沉浸课堂", ["generate_immersive_classroom"], ["generate_lesson_video"]),
         ("一键生成数据结构课程", ["generate_immersive_classroom"], ["generate_lesson_video"]),
         ("生成知识点讲解视频和沉浸课堂", ["generate_immersive_classroom"], ["generate_lesson_video"]),
         ("生成一份练习题", ["generate_quiz"], ["generate_explanation"]),
         ("制定学习计划并生成练习题", ["generate_learning_path", "generate_quiz"], []),
