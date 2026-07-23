# Review package: 20910de0cf7a0718941807cd0005482449683abe..HEAD

## Commits
ec543d1 fix: replan rejected agent tool calls
a222783 fix: harden agent runtime tool boundaries
e6c94d0 docs: add real provider acceptance status record
76b64e1 docs: record agent runtime convergence
fd62eb2 fix: close agent runtime transaction boundaries
0ffdfc1 fix: atomically claim and observe agent tasks
dc903e0 fix: preserve supervisor profile decision
e4b9664 refactor: isolate supervisor policy helpers
40da743 refactor: move supervisor argument policy
47128a8 refactor: separate supervisor responsibilities
5b8a280 refactor: split agent service toolsets
426a39a fix: honor skipped tools in selector fallback
fb9ca0f feat: limit agent tools by intent
cfa441e Normalize agent structured outputs and refresh nginx on deploy

## Files changed
 backend/app/agent_runtime/graph.py                 |   15 +-
 backend/app/agent_runtime/service_tools.py         |  906 +---------------
 backend/app/agent_runtime/supervisor.py            | 1120 ++------------------
 backend/app/agent_runtime/supervisor_completion.py |  129 +++
 backend/app/agent_runtime/supervisor_policy.py     |  290 +++++
 backend/app/agent_runtime/supervisor_prompt.py     |   66 ++
 backend/app/agent_runtime/tool_selector.py         |   66 ++
 backend/app/agent_runtime/tools.py                 |   13 +
 backend/app/agent_runtime/toolsets/__init__.py     |   13 +
 backend/app/agent_runtime/toolsets/common.py       |   39 +
 .../app/agent_runtime/toolsets/knowledge_tools.py  |  139 +++
 .../app/agent_runtime/toolsets/learning_tools.py   |  154 +++
 backend/app/agent_runtime/toolsets/media_tools.py  |  196 ++++
 .../app/agent_runtime/toolsets/profile_tools.py    |   91 ++
 backend/app/agent_runtime/toolsets/review_tools.py |   53 +
 backend/app/agents/structured_outputs.py           |   33 +-
 backend/app/repositories/agent_task_repository.py  |   14 +-
 backend/app/services/agent_runtime_service.py      |  117 +-
 backend/app/services/prompt_service.py             |    2 +-
 backend/tests/test_agent_cancellation.py           |  197 ++++
 backend/tests/test_agent_runtime.py                |  413 +++++++-
 .../tests/test_real_provider_acceptance_helpers.py |   23 +
 .../tests/test_structured_output_normalization.py  |   35 +
 backend/tests/test_supervisor_intents.py           |   33 +
 ...252\214\346\224\266\350\256\260\345\275\225.md" |   88 ++
 .../2026-07-11-real-provider-full-acceptance.md    |  318 ++++++
 ...256\236\347\216\260\345\237\272\347\272\277.md" |    3 +-
 scripts/fast_deploy_code.sh                        |    2 +
 scripts/real_provider_acceptance.py                |   26 +
 29 files changed, 2611 insertions(+), 1983 deletions(-)

## Diff
diff --git a/backend/app/agent_runtime/graph.py b/backend/app/agent_runtime/graph.py
index 3b2c5ee..42b9726 100644
--- a/backend/app/agent_runtime/graph.py
+++ b/backend/app/agent_runtime/graph.py
@@ -1,22 +1,24 @@
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
+from app.agent_runtime.tool_selector import select_tool_schemas
 from app.agent_runtime.tools import ToolContext, ToolRegistry
 from app.services.conversation_intent import is_simple_greeting
 
 
 StateHook = Callable[[AgentState], Awaitable[dict[str, Any]]]
 EventSink = Callable[[str, AgentState, dict[str, Any]], Awaitable[None]]
 
 
 class LearningAgentGraph:
     def __init__(
@@ -156,21 +158,25 @@ class LearningAgentGraph:
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
+        supervisor_started = time.perf_counter()
+        decision = await self.supervisor.decide(state, candidate_tool_schemas)
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
@@ -180,20 +186,23 @@ class LearningAgentGraph:
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
@@ -270,29 +279,33 @@ class LearningAgentGraph:
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
+        tool_started = time.perf_counter()
         result = await self.registry.execute(name, dict(call.get("arguments") or {}), context)
+        duration_ms = int((time.perf_counter() - tool_started) * 1000)
+        result.duration_ms = duration_ms
         await self.event_sink(
             "tool_completed",
             state,
             {
                 "tool_call_id": call["id"],
                 "tool_name": name,
                 "success": result.success,
                 "attempts": result.attempts,
+                "duration_ms": duration_ms,
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
diff --git a/backend/app/agent_runtime/service_tools.py b/backend/app/agent_runtime/service_tools.py
index 5b683a8..8015374 100644
--- a/backend/app/agent_runtime/service_tools.py
+++ b/backend/app/agent_runtime/service_tools.py
@@ -1,891 +1,47 @@
 from __future__ import annotations
 
-import json
-from typing import Any
-from uuid import UUID
-
 from sqlalchemy.ext.asyncio import AsyncSession
 
-from app.agent_runtime.tools import AgentTool, ToolContext, ToolExecutionResult, ToolRegistry
+from app.agent_runtime.tools import ToolRegistry
+from app.agent_runtime.toolsets import (
+    register_knowledge_tools,
+    register_learning_tools,
+    register_media_tools,
+    register_profile_tools,
+    register_review_tools,
+)
 from app.models.user import User
 
 
+def _register_toolsets(
+    registry: ToolRegistry,
+    db: AsyncSession,
+    current_user: User,
+) -> None:
+    # Preserve the registry's established public tool order.
+    register_knowledge_tools(registry, db, current_user, tool_names=("search_course_knowledge", "search_web"))
+    register_learning_tools(registry, db, current_user, tool_names=("answer_course_question", "generate_learning_path", "generate_explanation", "generate_quiz"))
+    register_knowledge_tools(registry, db, current_user, tool_names=("parse_uploaded_document", "generate_mindmap", "generate_diagram"))
+    register_media_tools(registry, db, current_user, tool_names=("transcribe_audio", "synthesize_speech"))
+    register_learning_tools(registry, db, current_user, tool_names=("analyze_learning_diagnosis", "refresh_recommendations"))
+    register_profile_tools(registry, db, current_user, tool_names=("update_profile_from_dialogue", "rebuild_profile", "reflect_learning_memory"))
+    register_review_tools(registry, db, current_user)
+    register_profile_tools(registry, db, current_user, tool_names=("apply_evolution_strategy",))
+    register_media_tools(registry, db, current_user, tool_names=("generate_educational_image", "generate_immersive_classroom", "generate_lesson_video", "generate_storyboard_html", "generate_interactive_courseware"))
+
+
 def build_learning_tool_registry(
     db: AsyncSession,
     current_user: User,
     *,
     result_loader=None,
     result_saver=None,
 ) -> ToolRegistry:
-    registry = ToolRegistry(result_loader=result_loader, result_saver=result_saver)
-
-    async def search_knowledge(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.services.knowledge_search_service import KnowledgeSearchService
-
-        payload = await KnowledgeSearchService(db).search(
-            current_user=current_user,
-            course_id=context.course_id,
-            query=str(arguments["query"]),
-            top_k=int(arguments.get("top_k") or 5),
-        )
-        items = payload.get("items") or []
-        graph_context = payload.get("graph_context") or {}
-        citations = [
-            {
-                "source_type": "document",
-                "title": item.get("source_title") or "课程资料",
-                "source_id": item.get("material_id"),
-                "chunk_id": item.get("chunk_id"),
-                "page_no": item.get("page_no"),
-                "score": item.get("score"),
-                "quote": str(item.get("content") or "")[:300],
-            }
-            for item in items
-        ]
-        return ToolExecutionResult(
-            output={"items": items, "graph_context": graph_context},
-            evidence=citations,
-            citations=citations,
-        )
-
-    async def search_web(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.services.web_search_service import WebSearchService
-
-        payload = await WebSearchService().search(
-            query=str(arguments["query"]),
-            max_results=int(arguments.get("max_results") or 5),
-            domain=str(arguments.get("domain") or "") or None,
-        )
-        citations = payload.get("citations") or []
-        return ToolExecutionResult(
-            output=payload,
-            evidence=citations,
-            citations=citations,
-        )
-
-    async def answer_question(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.schemas.tutor import TutorChatRequest
-        from app.services.grounded_qa_pipeline import GroundedQaPipeline
-
-        result = await GroundedQaPipeline(db).answer(
-            TutorChatRequest(
-                course_id=context.course_id,
-                conversation_id=context.conversation_id,
-                question=str(arguments["question"]),
-                top_k=int(arguments.get("top_k") or 5),
-            ),
-            current_user,
-            persist_conversation_messages=False,
-        )
-        data = result.model_dump(mode="json")
-        refs = [{"type": "tutor_answer", "id": str(result.message_id)}] if result.message_id else []
-        return ToolExecutionResult(
-            output=data,
-            evidence=data.get("citations") or [],
-            citations=data.get("citations") or [],
-            artifact_refs=refs,
-            final_answer=result.answer,
-        )
-
-    async def generate_path(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.schemas.learning_path import LearningPathGenerateRequest
-        from app.services.learning_path_service import LearningPathService
-
-        result = await LearningPathService(db).generate(
-            payload=LearningPathGenerateRequest(
-                course_id=context.course_id,
-                goal=str(arguments["goal"]),
-            ),
-            current_user=current_user,
-        )
-        data = result.model_dump(mode="json")
-        return ToolExecutionResult(
-            output=data,
-            evidence=[result.reason or "基于课程知识点、画像和目标生成"],
-            artifact_refs=[{"type": "learning_path", "id": str(result.id), "title": result.title}],
-        )
-
-    async def generate_explanation(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.schemas.resource import ResourceGenerateRequest
-        from app.services.resource_service import ResourceService
-
-        topic = str(arguments["topic"])
-        result = await ResourceService(db).generate_resource(
-            payload=ResourceGenerateRequest(
-                course_id=context.course_id,
-                resource_type=str(arguments.get("resource_type") or "explanation"),
-                requirement=str(arguments.get("requirement") or f"围绕{topic}生成分步骤讲解并引用课程资料。"),
-                use_profile=True,
-            ),
-            current_user=current_user,
-        )
-        data = result.model_dump(mode="json")
-        return ToolExecutionResult(
-            output=data,
-            evidence=data.get("citations") or [],
-            citations=data.get("citations") or [],
-            artifact_refs=[
-                {
-                    "type": "resource",
-                    "subtype": data.get("resource_type"),
-                    "resource_type": data.get("resource_type"),
-                    "id": str(result.resource_id),
-                    "resource_id": str(result.resource_id),
-                    "title": result.title,
-                }
-            ],
-        )
-
-    async def generate_quiz(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.schemas.quiz import QuizGenerateRequest
-        from app.services.quiz_service import QuizService
-
-        result = await QuizService(db).generate_quiz(
-            payload=QuizGenerateRequest(
-                course_id=context.course_id,
-                topic=str(arguments["topic"]),
-                count=int(arguments.get("count") or 5),
-                difficulty=str(arguments.get("difficulty") or "medium"),
-                question_types=list(arguments.get("question_types") or ["single_choice"]),
-            ),
-            current_user=current_user,
-        )
-        data = result.model_dump(mode="json")
-        return ToolExecutionResult(
-            output=data,
-            evidence=[f"生成 {len(result.questions)} 道结构化练习"],
-            artifact_refs=[{"type": "quiz", "id": str(result.quiz_id), "title": result.title}],
-        )
-
-    async def parse_document(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.services.embedding_service import EmbeddingService
-        from app.services.material_service import MaterialService
-
-        material_id = UUID(str(arguments["material_id"]))
-        parse_result = await MaterialService(db).parse_material(
-            material_id=material_id,
-            current_user=current_user,
-        )
-        embedded_count = await EmbeddingService(db).generate_embeddings(material_id)
-        return ToolExecutionResult(
-            output={
-                "material_id": str(material_id),
-                "file_name": parse_result.file_name,
-                "text_length": parse_result.text_length,
-                "parse_status": parse_result.parse_status,
-                "embedded_count": embedded_count,
-            },
-            evidence=[
-                f"已解析 {parse_result.file_name}，提取 {parse_result.text_length} 字符",
-                f"已生成 {embedded_count} 个向量切片",
-            ],
-            artifact_refs=[
-                {
-                    "type": "material",
-                    "id": str(material_id),
-                    "title": parse_result.file_name,
-                }
-            ],
-        )
-
-    async def generate_mindmap_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.services.mindmap_service import MindmapService
-
-        topic = str(arguments.get("topic") or "").strip() or "数据结构知识结构"
-        result = await MindmapService(db).generate(
-            current_user=current_user,
-            course_id=context.course_id,
-            topic=topic,
-            scope=str(arguments.get("scope") or "course"),
-            depth=int(arguments.get("depth") or 3),
-        )
-        return ToolExecutionResult(
-            output=result,
-            evidence=result.get("citations") or [],
-            citations=result.get("citations") or [],
-            artifact_refs=[
-                {
-                    "type": "resource",
-                    "subtype": "mindmap",
-                    "id": result["resource_id"],
-                    "title": result["title"],
-                }
-            ],
-        )
-
-    async def generate_diagram_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.services.diagram_service import DiagramService
-
-        concept = str(arguments.get("concept") or "").strip() or "数据结构概念"
-        result = await DiagramService(db).generate(
-            current_user=current_user,
-            course_id=context.course_id,
-            concept=concept,
-            diagram_type=str(arguments.get("diagram_type") or "flowchart"),
-        )
-        return ToolExecutionResult(
-            output=result,
-            evidence=result.get("citations") or [],
-            citations=result.get("citations") or [],
-            artifact_refs=[
-                {
-                    "type": "resource",
-                    "subtype": "diagram",
-                    "id": result["resource_id"],
-                    "title": result["title"],
-                }
-            ],
-        )
-
-    async def transcribe_audio_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.llm.audio_provider import _safe_audio_byte_count, build_audio_provider
-
-        audio_base64 = str(arguments["audio_base64"])
-        byte_count = _safe_audio_byte_count(audio_base64)
-        result = await build_audio_provider().transcribe(
-            audio_base64,
-            filename=str(arguments.get("filename") or "audio.wav"),
-            language=str(arguments.get("language") or "zh"),
-        )
-        raw = result.raw or {}
-        return ToolExecutionResult(
-            output={
-                "text": result.text,
-                "duration_ms": result.duration_ms,
-                "language": result.language,
-                "provider": result.provider,
-                "model": result.model,
-                "audio_bytes": byte_count,
-                "fallback_used": bool(raw.get("fallback_used")),
-                "failed_provider": raw.get("failed_provider"),
-                "fallback_reason": raw.get("fallback_reason"),
-            },
-            evidence=[
-                f"语音识别完成，provider={result.provider}，模型={result.model}",
-                f"输入音频 {byte_count} bytes，识别文本 {len(result.text)} 字",
-            ],
-        )
-
-    async def synthesize_speech_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        import base64
-
-        from app.llm.audio_provider import (
-            MIMO_TTS_MODEL,
-            MIMO_TTS_VOICECLONE_MODEL,
-            MIMO_TTS_VOICEDESIGN_MODEL,
-            build_audio_provider,
-        )
-        from app.repositories.media_repository import MediaRepository
-        from app.services.media_storage_service import MediaStorageService
-
-        text = str(arguments["text"]).strip()
-        model_type = str(arguments.get("model_type") or "tts")
-        model_map = {
-            "tts": MIMO_TTS_MODEL,
-            "voiceclone": MIMO_TTS_VOICECLONE_MODEL,
-            "voicedesign": MIMO_TTS_VOICEDESIGN_MODEL,
-        }
-        result = await build_audio_provider().synthesize(
-            text,
-            voice=str(arguments.get("voice") or "") or None,
-            speed=float(arguments.get("speed") or 1.0),
-            response_format=str(arguments.get("response_format") or "wav"),
-            model=model_map.get(model_type, MIMO_TTS_MODEL),
-        )
-        raw = result.raw or {}
-        audio_format = result.format or "wav"
-        padding = "=" * (-len(result.audio_base64) % 4)
-        audio_bytes = base64.b64decode(result.audio_base64 + padding)
-        storage_path, file_size, mime_type = MediaStorageService().save_bytes(
-            data=audio_bytes,
-            asset_type="audio",
-            suffix=f".{audio_format}",
-        )
-        topic = text[:30].replace("\n", " ")
-        asset = await MediaRepository(db).create_asset(
-            user_id=current_user.id,
-            course_id=context.course_id,
-            asset_type="audio",
-            title=f"语音讲解 · {topic}",
-            storage_path=storage_path,
-            mime_type=mime_type,
-            file_size=file_size,
-            duration_ms=result.duration_ms,
-            agent_task_id=context.task_id,
-            tool_call_id=context.tool_call_id,
-            provider=result.provider,
-            model_name=result.model,
-            prompt=text[:2000],
-        )
-        return ToolExecutionResult(
-            output={
-                "asset_id": str(asset.id),
-                "audio_base64": result.audio_base64,
-                "format": audio_format,
-                "model": result.model,
-                "provider": result.provider,
-                "duration_ms": result.duration_ms,
-                "text_length": len(text),
-                "fallback_used": bool(raw.get("fallback_used")),
-                "failed_provider": raw.get("failed_provider"),
-                "fallback_reason": raw.get("fallback_reason"),
-            },
-            evidence=[
-                f"语音合成完成，provider={result.provider}，模型={result.model}",
-                f"输出格式 {audio_format}，文本 {len(text)} 字",
-            ],
-            artifact_refs=[
-                {
-                    "type": "audio",
-                    "asset_id": str(asset.id),
-                    "title": asset.title,
-                    "mime_type": mime_type,
-                }
-            ],
-        )
-
-    async def analyze_diagnosis(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.services.diagnosis_service import DiagnosisService
-
-        result = await DiagnosisService(db).analyze(
-            current_user=current_user,
-            course_id=context.course_id,
-            trigger_evolution=False,
-        )
-        return ToolExecutionResult(
-            output=result,
-            evidence=result.get("weak_points") or [],
-            artifact_refs=[{"type": "diagnosis_report", "id": str(result.get("id") or "")}],
-        )
-
-    async def refresh_recommendations(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.services.recommendation_service import RecommendationService
-
-        result = await RecommendationService(db).refresh_recommendations(
-            current_user=current_user,
-            course_id=context.course_id,
-        )
-        return ToolExecutionResult(
-            output=result,
-            evidence=["基于画像、诊断与学习路径刷新"],
-            artifact_refs=[{"type": "recommendations", "count": result["refreshed_count"]}],
-        )
-
-    async def rebuild_profile(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.services.profile_service import ProfileService
-
-        result = await ProfileService(db).rebuild(current_user.id)
-        data = result.model_dump(mode="json")
-        return ToolExecutionResult(
-            output=data,
-            evidence=["基于当前用户学习记录重建"],
-            artifact_refs=[{"type": "profile_update", "id": str(result.id)}],
-        )
-
-    async def update_profile_from_dialogue(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.services.profile_service import ProfileService
-
-        result = await ProfileService(db).ingest_dialogue_profile(
-            user_id=current_user.id,
-            course_id=context.course_id,
-            dialogue_text=str(arguments["dialogue_text"]),
-            source_message_id=str(arguments.get("source_message_id") or context.tool_call_id),
-        )
-        data = result.model_dump(mode="json")
-        artifact_refs = [{"type": "profile_update", "id": str(result.profile.id)}]
-        if result.preferences is not None:
-            artifact_refs.append({"type": "learning_preference", "id": str(result.preferences.id)})
-        return ToolExecutionResult(
-            output=data,
-            evidence=[data.get("evidence") or {}],
-            artifact_refs=artifact_refs,
-        )
-
-    async def reflect_memory(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.services.memory_service import MemoryService
-
-        results = await MemoryService(db).reflect(current_user.id, context.course_id)
-        data = [item.model_dump(mode="json") for item in results]
-        return ToolExecutionResult(
-            output={"items": data},
-            evidence=[{"memory_id": str(item.id), "evidence": item.evidence} for item in results],
-            artifact_refs=[{"type": "memory_reflection", "count": len(results)}],
-        )
-
-    async def review_artifacts(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.services.agent_service import AgentService
-
-        result = await AgentService(db).run_task(
-            task_type="review_content",
-            user_id=current_user.id,
-            course_id=context.course_id,
-            params={"content": str(arguments.get("content") or "")[:4000]},
-        )
-        if not result.success:
-            raise RuntimeError(result.message)
-        return ToolExecutionResult(output=result.data, evidence=result.evidence)
-
-    async def review_multimodal_asset_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.services.multimodal_review_service import MultimodalReviewService
-
-        asset_id = UUID(str(arguments["asset_id"]))
-        result = await MultimodalReviewService(db).review_asset(asset_id, current_user.id)
-        return ToolExecutionResult(
-            output=result,
-            evidence=[
-                f"多模态审核完成，risk={result['risk_level']}，引用 {result['citation_count']} 条",
-                *(result.get("issues") or []),
-            ],
-            artifact_refs=[
-                {
-                    "type": "media_review",
-                    "asset_id": result["asset_id"],
-                    "risk_level": result["risk_level"],
-                    "passed": result["passed"],
-                }
-            ],
-        )
-
-    async def apply_evolution(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.services.evolution_service import EvolutionService
-
-        service = EvolutionService(db)
-        strategy_id = arguments.get("strategy_id")
-        if not strategy_id:
-            items, _ = await service.list_strategies(
-                user_id=current_user.id,
-                course_id=context.course_id,
-                status="draft",
-                page_size=1,
-            )
-            if not items:
-                raise RuntimeError("当前没有可应用的草稿自进化策略")
-            strategy_id = items[0].id
-        result = await service.apply_strategy(UUID(str(strategy_id)), current_user.id)
-        return ToolExecutionResult(
-            output=result.model_dump(mode="json"),
-            artifact_refs=[{"type": "evolution_strategy", "id": str(result.id), "status": result.status}],
-        )
-
-    async def generate_educational_image_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.services.multimodal_resource_service import MultimodalResourceService
-
-        result = await MultimodalResourceService(db).generate_image(
-            current_user=current_user,
-            course_id=context.course_id,
-            topic=str(arguments["topic"]),
-            image_type=str(arguments.get("image_type") or "concept_illustration"),
-            style=str(arguments.get("style") or "clean educational illustration"),
-            size=str(arguments.get("size") or "1280x720"),
-            requirement=str(arguments.get("requirement") or "") or None,
-            tool_context=context,
-        )
-        mode = str(result.get("generation_mode") or "image")
-        if mode.startswith("mermaid"):
-            subtype = str(result.get("subtype") or "mindmap")
-            return ToolExecutionResult(
-                output=result,
-                evidence=result.get("citations") or [],
-                citations=result.get("citations") or [],
-                artifact_refs=[
-                    {
-                        "type": "resource",
-                        "subtype": subtype,
-                        "id": result["resource_id"],
-                        "title": result.get("title"),
-                    }
-                ],
-            )
-        return ToolExecutionResult(
-            output=result,
-            evidence=result.get("citations") or [],
-            citations=result.get("citations") or [],
-            artifact_refs=[{"type": "media_asset", "subtype": "image", **result}],
-        )
-
-    async def generate_lesson_video_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.services.multimodal_resource_service import MultimodalResourceService
-
-        result = await MultimodalResourceService(db).create_video_job(
-            current_user=current_user,
-            course_id=context.course_id,
-            topic=str(arguments["topic"]),
-            duration_seconds=int(arguments.get("duration_seconds") or 90),
-            visual_mode=str(arguments.get("visual_mode") or "storyboard"),
-            voice=str(arguments.get("voice") or "") or None,
-            target_level=str(arguments.get("target_level") or "") or None,
-            tool_context=context,
-        )
-        return ToolExecutionResult(
-            output=result,
-            evidence=["视频生成任务已创建，后台会持续写入进度事件。"],
-            artifact_refs=[{"type": "media_job", "subtype": "video", **result}],
-        )
-
-    async def generate_immersive_classroom_handler(
-        context: ToolContext,
-        arguments: dict[str, Any],
-    ) -> ToolExecutionResult:
-        from app.services.immersive_classroom_service import ImmersiveClassroomService
-
-        result = await ImmersiveClassroomService(db).create_job(
-            current_user=current_user,
-            course_id=context.course_id,
-            topic=str(arguments["topic"]),
-            learning_goal=str(arguments.get("learning_goal") or "") or None,
-            generate_video_export=bool(arguments.get("generate_video_export", True)),
-            enable_images=bool(arguments.get("enable_images", True)),
-            enable_video_clips=bool(arguments.get("enable_video_clips", False)),
-            enable_tts=bool(arguments.get("enable_tts", True)),
-            tool_context=context,
-        )
-        return ToolExecutionResult(
-            output=result,
-            evidence=["已创建基于课程 RAG 与学生画像的沉浸课堂任务，后台将继续生成课堂和配音字幕 MP4。"],
-            artifact_refs=[{"type": "media_job", "subtype": "immersive_classroom", **result}],
-        )
-
-    async def generate_storyboard_html_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.services.multimodal_resource_service import MultimodalResourceService
-
-        result = await MultimodalResourceService(db).generate_storyboard_html(
-            current_user=current_user,
-            course_id=context.course_id,
-            topic=str(arguments["topic"]),
-            duration_seconds=int(arguments.get("duration_seconds") or 90),
-            requirement=str(arguments.get("requirement") or "") or None,
-            tool_context=context,
-        )
-        return ToolExecutionResult(
-            output=result,
-            evidence=result.get("citations") or [],
-            citations=result.get("citations") or [],
-            artifact_refs=[{"type": "media_asset", "subtype": "storyboard", **result}],
-        )
-
-    async def generate_interactive_courseware_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
-        from app.services.multimodal_resource_service import MultimodalResourceService
-
-        result = await MultimodalResourceService(db).generate_courseware(
-            current_user=current_user,
-            course_id=context.course_id,
-            topic=str(arguments["topic"]),
-            interaction_type=str(arguments.get("interaction_type") or "stepper"),
-            target_level=str(arguments.get("target_level") or "") or None,
-            requirement=str(arguments.get("requirement") or "") or None,
-            tool_context=context,
-        )
-        return ToolExecutionResult(
-            output=result,
-            evidence=result.get("citations") or [],
-            citations=result.get("citations") or [],
-            artifact_refs=[{"type": "media_asset", "subtype": "courseware", **result}],
-        )
-
-    _register(
-        registry,
-        name="search_course_knowledge",
-        description="使用向量、关键词、metadata 和 rerank 混合检索课程资料，返回可引用片段。",
-        agent_name="KnowledgeAgent",
-        properties={"query": {"type": "string"}, "top_k": {"type": "integer", "minimum": 1, "maximum": 20}},
-        required=["query"],
-        handler=search_knowledge,
-    )
-    _register(
-        registry,
-        name="search_web",
-        description="通过 AnySearch 联网搜索互联网实时信息，返回可引用的网页标题、URL 与摘要。适用于最新资讯、公开资料、技术文档等课程库未覆盖的问题。",
-        agent_name="KnowledgeAgent",
-        properties={
-            "query": {"type": "string", "description": "搜索关键词或完整问题"},
-            "max_results": {"type": "integer", "minimum": 1, "maximum": 10},
-            "domain": {
-                "type": "string",
-                "description": "可选垂直领域，如 general/academic/code/finance",
-            },
-        },
-        required=["query"],
-        handler=search_web,
-        timeout_seconds=45,
-    )
-    _register(
-        registry,
-        name="answer_course_question",
-        description="基于课程知识库、Wiki 和学生画像回答学习问题。",
-        agent_name="TutorAgent",
-        properties={"question": {"type": "string"}, "top_k": {"type": "integer", "minimum": 1, "maximum": 20}},
-        required=["question"],
-        handler=answer_question,
-        writes_db=True,
-    )
-    _register(
-        registry,
-        name="generate_learning_path",
-        description="根据学习目标、薄弱点和课程知识点生成个性化学习路径。",
-        agent_name="PlannerAgent",
-        properties={"goal": {"type": "string"}},
-        required=["goal"],
-        handler=generate_path,
-        writes_db=True,
-    )
-    _register(
-        registry,
-        name="generate_explanation",
-        description="围绕知识主题生成带来源和个性化理由的学习资源。",
-        agent_name="ResourceAgent",
-        properties={
-            "topic": {"type": "string"},
-            "resource_type": {"type": "string", "enum": ["explanation", "summary", "example", "flashcard", "review"]},
-            "requirement": {"type": "string"},
-        },
-        required=["topic"],
-        handler=generate_explanation,
-        writes_db=True,
-    )
-    _register(
-        registry,
-        name="generate_quiz",
-        description="围绕主题生成结构化练习题。",
-        agent_name="QuizAgent",
-        properties={
-            "topic": {"type": "string"},
-            "count": {"type": "integer", "minimum": 1, "maximum": 20},
-            "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
-            "question_types": {"type": "array", "items": {"type": "string"}},
-        },
-        required=["topic"],
-        handler=generate_quiz,
-        writes_db=True,
-    )
-    _register(
-        registry,
-        name="parse_uploaded_document",
-        description="解析已上传的课程资料（PDF/DOCX/TXT/MD），自动切片和向量化，供 RAG 检索使用。",
-        agent_name="KnowledgeAgent",
-        properties={"material_id": {"type": "string", "description": "课程资料 UUID"}},
-        required=["material_id"],
-        handler=parse_document,
-        writes_db=True,
+    registry = ToolRegistry(
+        result_loader=result_loader,
+        result_saver=result_saver,
+        on_handler_error=lambda _error: db.rollback(),
     )
-    _register(
-        registry,
-        name="generate_mindmap",
-        description="围绕课程知识点生成 Mermaid 思维导图，可视化知识结构关系。",
-        agent_name="KnowledgeAgent",
-        properties={
-            "topic": {"type": "string", "description": "知识主题"},
-            "scope": {"type": "string", "enum": ["course", "chapter", "custom"]},
-            "depth": {"type": "integer", "minimum": 2, "maximum": 5},
-        },
-        required=["topic"],
-        handler=generate_mindmap_handler,
-        writes_db=True,
-    )
-    _register(
-        registry,
-        name="generate_diagram",
-        description="围绕知识概念生成流程图、架构图或示意图的 Mermaid 代码。",
-        agent_name="KnowledgeAgent",
-        properties={
-            "concept": {"type": "string", "description": "需要图解的概念"},
-            "diagram_type": {"type": "string", "enum": ["flowchart", "sequence", "class", "er"]},
-        },
-        required=["concept"],
-        handler=generate_diagram_handler,
-        writes_db=True,
-    )
-    _register(
-        registry,
-        name="transcribe_audio",
-        description="将音频文件转换为文字，支持语音提问、语音笔记等场景。",
-        agent_name="TutorAgent",
-        properties={
-            "audio_base64": {"type": "string", "description": "Base64 编码的音频数据"},
-            "filename": {"type": "string", "description": "文件名（用于推断格式）"},
-            "language": {"type": "string", "description": "语言代码，默认 zh"},
-        },
-        required=["audio_base64"],
-        handler=transcribe_audio_handler,
-        timeout_seconds=60,
-    )
-    _register(
-        registry,
-        name="synthesize_speech",
-        description="将文字转换为语音，用于讲解朗读、错题语音反馈等场景。",
-        agent_name="TutorAgent",
-        properties={
-            "text": {"type": "string", "description": "要转换的文字"},
-            "model_type": {"type": "string", "enum": ["tts", "voiceclone", "voicedesign"]},
-            "voice": {"type": "string", "description": "音色，可由具体 Provider 解释"},
-            "speed": {"type": "number", "minimum": 0.5, "maximum": 2.0},
-            "response_format": {"type": "string", "enum": ["wav", "mp3"]},
-        },
-        required=["text"],
-        handler=synthesize_speech_handler,
-        timeout_seconds=120,
-    )
-    _register(registry, "analyze_learning_diagnosis", "基于练习和错题生成学习诊断。", "DiagnosisAgent", {}, [], analyze_diagnosis, writes_db=True)
-    _register(registry, "refresh_recommendations", "根据画像、诊断和路径刷新推荐。", "RecommendAgent", {}, [], refresh_recommendations, writes_db=True)
-    _register(
-        registry,
-        "update_profile_from_dialogue",
-        "从学生自然语言对话中提取学习目标、专业年级、偏好、薄弱点和错误模式，并带证据更新画像。",
-        "ProfileAgent",
-        {
-            "dialogue_text": {"type": "string"},
-            "source_message_id": {"type": "string"},
-        },
-        ["dialogue_text"],
-        update_profile_from_dialogue,
-        writes_db=True,
-    )
-    _register(registry, "rebuild_profile", "基于学习证据重建学生画像。", "ProfileAgent", {}, [], rebuild_profile, writes_db=True)
-    _register(registry, "reflect_learning_memory", "提炼带证据的长期学习记忆。", "MemoryAgent", {}, [], reflect_memory, writes_db=True)
-    _register(
-        registry,
-        "review_artifacts",
-        "审查生成内容的来源、幻觉和风险。",
-        "ReviewAgent",
-        {"content": {"type": "string"}},
-        ["content"],
-        review_artifacts,
-    )
-    _register(
-        registry,
-        "review_multimodal_asset",
-        "审核图片、视频、互动课件等多模态产物的事实依据、安全风险、版权风险与可访问性。",
-        "ReviewAgent",
-        {"asset_id": {"type": "string", "minLength": 1}},
-        ["asset_id"],
-        review_multimodal_asset_handler,
-    )
-    _register(
-        registry,
-        "apply_evolution_strategy",
-        "应用已生成的自进化策略。该操作必须获得用户确认。",
-        "EvolutionAgent",
-        {"strategy_id": {"type": "string"}},
-        [],
-        apply_evolution,
-        writes_db=True,
-        risk_level="high",
-        requires_confirmation=True,
-    )
-    _register(
-        registry,
-        name="generate_educational_image",
-        description="基于课程资料、学生画像和知识主题生成教学插图、概念图、类比图或封面图。",
-        agent_name="VisualResourceAgent",
-        properties={
-            "topic": {"type": "string", "minLength": 1},
-            "image_type": {"type": "string", "enum": ["concept_illustration", "process_visual", "analogy", "cover", "summary_card"]},
-            "style": {"type": "string"},
-            "size": {"type": "string", "enum": ["1024x1024", "1280x720", "720x1280", "1024x768"]},
-            "requirement": {"type": "string"},
-        },
-        required=["topic"],
-        handler=generate_educational_image_handler,
-        writes_db=True,
-        timeout_seconds=180,
-    )
-    _register(
-        registry,
-        name="generate_immersive_classroom",
-        description="基于课程资料、学生画像与薄弱点，一键生成 OpenMAIC 沉浸课堂，并可导出配音字幕知识点讲解 MP4。",
-        agent_name="ImmersiveClassroomAgent",
-        properties={
-            "topic": {"type": "string", "minLength": 1},
-            "learning_goal": {"type": "string"},
-            "generate_video_export": {"type": "boolean"},
-            "enable_images": {"type": "boolean"},
-            "enable_video_clips": {"type": "boolean"},
-            "enable_tts": {"type": "boolean"},
-        },
-        required=["topic"],
-        handler=generate_immersive_classroom_handler,
-        writes_db=True,
-        timeout_seconds=30,
-    )
-    _register(
-        registry,
-        name="generate_lesson_video",
-        description="创建短讲解视频（MP4）生成任务。仅当用户明确要「视频/短视频/动画讲解」时使用；PPT/幻灯片/课件应使用 generate_interactive_courseware。",
-        agent_name="VideoResourceAgent",
-        properties={
-            "topic": {"type": "string", "minLength": 1},
-            "duration_seconds": {"type": "integer", "minimum": 30, "maximum": 240},
-            "visual_mode": {"type": "string", "enum": ["storyboard", "animated_diagram", "t2v_broll", "mixed"]},
-            "voice": {"type": "string"},
-            "target_level": {"type": "string"},
-        },
-        required=["topic"],
-        handler=generate_lesson_video_handler,
-        writes_db=True,
-        timeout_seconds=30,
-    )
-    _register(
-        registry,
-        name="generate_storyboard_html",
-        description="基于课程资料生成分镜 HTML 讲解页，可在 sandbox iframe 中预览（文生视频演示替代）。",
-        agent_name="VideoResourceAgent",
-        properties={
-            "topic": {"type": "string", "minLength": 1},
-            "duration_seconds": {"type": "integer", "minimum": 30, "maximum": 240},
-            "requirement": {"type": "string"},
-        },
-        required=["topic"],
-        handler=generate_storyboard_html_handler,
-        writes_db=True,
-        timeout_seconds=120,
-    )
-    _register(
-        registry,
-        name="generate_interactive_courseware",
-        description="基于 html-ppt-skill 生成多页 HTML 互动课件（PPT/幻灯片/slides/deck）。用户要 ppt、课件、幻灯片、翻页演示时用此工具，不是讲解视频。",
-        agent_name="CoursewareAgent",
-        properties={
-            "topic": {"type": "string", "minLength": 1},
-            "interaction_type": {"type": "string", "enum": ["stepper", "drag_sort", "quiz_simulation", "graph_traversal", "timeline"]},
-            "target_level": {"type": "string"},
-            "requirement": {"type": "string"},
-        },
-        required=["topic"],
-        handler=generate_interactive_courseware_handler,
-        writes_db=True,
-        timeout_seconds=180,
-    )
-    return registry
-
 
-def _register(
-    registry: ToolRegistry,
-    name: str,
-    description: str,
-    agent_name: str,
-    properties: dict[str, Any],
-    required: list[str],
-    handler,
-    *,
-    writes_db: bool = False,
-    risk_level: str = "low",
-    requires_confirmation: bool = False,
-    timeout_seconds: int = 120,
-) -> None:
-    registry.register(
-        AgentTool(
-            name=name,
-            description=description,
-            agent_name=agent_name,
-            input_schema={
-                "type": "object",
-                "properties": properties,
-                "required": required,
-                "additionalProperties": False,
-            },
-            handler=handler,
-            writes_db=writes_db,
-            risk_level=risk_level,  # type: ignore[arg-type]
-            requires_confirmation=requires_confirmation,
-            timeout_seconds=timeout_seconds,
-        )
-    )
+    _register_toolsets(registry, db, current_user)
+    return registry
diff --git a/backend/app/agent_runtime/supervisor.py b/backend/app/agent_runtime/supervisor.py
index a072aa8..58ff010 100644
--- a/backend/app/agent_runtime/supervisor.py
+++ b/backend/app/agent_runtime/supervisor.py
@@ -1,1090 +1,112 @@
 from __future__ import annotations
 
 import json
 from typing import Any, Protocol
 from uuid import uuid4
 
 from pydantic import ValidationError
 
 from app.agent_runtime.answer_text import extract_final_answer_text
-from app.agent_runtime.state import AgentDecision, PlannedToolCall
 from app.agent_runtime import supervisor_intents
-from app.llm.schemas import ChatMessage, ToolCall
+from app.agent_runtime.supervisor_completion import build_completion_answer, build_search_results_answer, format_search_output_answer, normalize_completion_answer
+from app.agent_runtime.supervisor_policy import SupervisorPolicy, _resolve_speech_text, _topic_for_tool, apply_safety_net, safe_arguments
+from app.agent_runtime.supervisor_prompt import build_messages
+from app.agent_runtime.state import AgentDecision, PlannedToolCall
+from app.llm.schemas import ChatMessage
 from app.services.conversation_intent import is_simple_greeting, simple_greeting_answer
 
 
 class Supervisor(Protocol):
-    async def decide(
-        self,
-        state: dict[str, Any],
-        tool_schemas: list[dict[str, Any]],
-    ) -> AgentDecision:
-        ...
+    async def decide(self, state: dict[str, Any], tool_schemas: list[dict[str, Any]]) -> AgentDecision: ...
 
 
 class MiMoSupervisor:
     def __init__(self, provider: object) -> None:
         self.provider = provider
+        self._policy = SupervisorPolicy()
 
-    async def decide(
-        self,
-        state: dict[str, Any],
-        tool_schemas: list[dict[str, Any]],
-    ) -> AgentDecision:
+    async def decide(self, state: dict[str, Any], tool_schemas: list[dict[str, Any]]) -> AgentDecision:
         if is_simple_greeting(str(state.get("goal") or "")):
-            return AgentDecision(
-                status="complete",
-                summary="轻量寒暄直接响应。",
-                final_answer=simple_greeting_answer(),
-            )
-        bounded_decision = self._profile_update_only_decision(state, tool_schemas)
-        if bounded_decision is not None:
-            return bounded_decision
-        early_complete = self._deliverables_complete_decision(state, tool_schemas)
-        if early_complete is not None:
-            return early_complete
-        intent_first = self._intent_first_decision(state, tool_schemas)
-        if intent_first is not None:
-            return self._apply_safety_net(state, tool_schemas, intent_first)
-        messages = self._build_messages(state)
-        chat_kwargs: dict[str, Any] = {
-            "thinking": {"type": "disabled"},
-        }
+            return AgentDecision(status="complete", summary="轻量寒暄直接响应。", final_answer=simple_greeting_answer())
+        bounded = self._profile_update_only_decision(state, tool_schemas)
+        if bounded is not None:
+            return bounded
+        complete = self._deliverables_complete_decision(state, tool_schemas)
+        if complete is not None:
+            return complete
+        intent = self._intent_first_decision(state, tool_schemas)
+        if intent is not None:
+            return self._apply_safety_net(state, tool_schemas, intent)
+        kwargs: dict[str, Any] = {"thinking": {"type": "disabled"}}
         if tool_schemas:
-            chat_kwargs["tools"] = tool_schemas
-            chat_kwargs["tool_choice"] = "auto"
+            kwargs.update(tools=tool_schemas, tool_choice="auto")
         else:
-            chat_kwargs["response_format"] = {"type": "json_object"}
-        response = await self.provider.chat(messages, **chat_kwargs)
+            kwargs["response_format"] = {"type": "json_object"}
+        response = await self.provider.chat(self._build_messages(state), **kwargs)
         if response.tool_calls:
-            decision = AgentDecision(
-                status="continue",
-                summary="Supervisor 根据当前目标选择了下一组工具。",
-                plan=[f"调用 {item.name}" for item in response.tool_calls],
-                tool_calls=[
-                    PlannedToolCall(
-                        id=item.id or f"call_{uuid4().hex}",
-                        name=item.name,
-                        arguments=item.arguments,
-                    )
-                    for item in response.tool_calls
-                ],
-                reasoning_content=response.reasoning_content,
-            )
-            return self._apply_safety_net(state, tool_schemas, decision)
-        decision = self._parse_decision(response.content)
-        decision.reasoning_content = response.reasoning_content
+            decision = AgentDecision(status="continue", summary="Supervisor 根据当前目标选择了下一组工具。", plan=[f"调用 {item.name}" for item in response.tool_calls], tool_calls=[PlannedToolCall(id=item.id or f"call_{uuid4().hex}", name=item.name, arguments=item.arguments) for item in response.tool_calls], reasoning_content=response.reasoning_content)
+        else:
+            decision = self._parse_decision(response.content)
+            decision.reasoning_content = response.reasoning_content
         return self._apply_safety_net(state, tool_schemas, decision)
 
     def _parse_decision(self, content: str) -> AgentDecision:
         try:
             data = json.loads(content)
             if isinstance(data, dict) and "status" in data:
-                data = self._normalize_decision_payload(data)
-                decision = AgentDecision.model_validate(data)
-                if decision.tool_calls and decision.status == "complete":
-                    decision.status = "continue"
-                if decision.final_answer:
-                    decision.final_answer = extract_final_answer_text(decision.final_answer)
+                decision = AgentDecision.model_validate(self._normalize_decision_payload(data))
+                if decision.tool_calls and decision.status == "complete": decision.status = "continue"
+                if decision.final_answer: decision.final_answer = extract_final_answer_text(decision.final_answer)
                 return decision
             if isinstance(data, dict):
-                raw_calls = data.get("tool_calls")
-                if isinstance(raw_calls, list) and raw_calls:
-                    calls = []
-                    for item in raw_calls:
-                        if not isinstance(item, dict):
-                            continue
-                        name = item.get("tool_name") or item.get("name")
-                        if not name:
-                            continue
-                        calls.append(
-                            PlannedToolCall(
-                                id=str(item.get("id") or f"call_{uuid4().hex}"),
-                                name=str(name),
-                                arguments=dict(item.get("parameters") or item.get("arguments") or {}),
-                            )
-                        )
-                    if calls:
-                        summary = str(data.get("decision") or data.get("summary") or "继续调用专业工具。")
-                        return AgentDecision(
-                            status="continue",
-                            summary=summary[:1000],
-                            plan=[summary[:1000]],
-                            tool_calls=calls,
-                        )
+                calls = [PlannedToolCall(id=str(item.get("id") or f"call_{uuid4().hex}"), name=str(item.get("tool_name") or item.get("name")), arguments=dict(item.get("parameters") or item.get("arguments") or {})) for item in data.get("tool_calls") or [] if isinstance(item, dict) and (item.get("tool_name") or item.get("name"))]
+                if calls:
+                    summary = str(data.get("decision") or data.get("summary") or "继续调用专业工具。")
+                    return AgentDecision(status="continue", summary=summary[:1000], plan=[summary[:1000]], tool_calls=calls)
                 answer = data.get("final_answer") or data.get("answer")
-                if answer:
-                    return AgentDecision(
-                        status="complete",
-                        summary=str(data.get("decision") or data.get("summary") or "任务完成")[:1000],
-                        final_answer=str(answer),
-                    )
+                if answer: return AgentDecision(status="complete", summary=str(data.get("decision") or data.get("summary") or "任务完成")[:1000], final_answer=str(answer))
         except (json.JSONDecodeError, ValidationError, TypeError):
             pass
-        extracted = extract_final_answer_text(content)
-        if extracted:
-            return AgentDecision(
-                status="complete",
-                summary="Supervisor 直接完成回答。",
-                final_answer=extracted,
-            )
-        return AgentDecision(
-            status="failed",
-            summary="Supervisor 未返回可执行决策。",
-            final_answer="智能体未能生成有效计划，请补充目标后重试。",
-        )
-
-    def _apply_safety_net(
-        self,
-        state: dict[str, Any],
-        tool_schemas: list[dict[str, Any]],
-        decision: AgentDecision,
-    ) -> AgentDecision:
-        """LLM 决策优先；仅在交付物缺失、显式约束或 LLM 空转时介入。"""
-        goal = str(state.get("goal") or "")
-        available = self._available_tool_names(tool_schemas)
-        completed_tools = self._completed_tool_names(state)
-        skip_tools = set(state.get("skip_tools") or [])
-
-        observations = list(state.get("observations") or [])
-        if observations and observations[-1].get("success") is False:
-            err = str(observations[-1].get("error_message") or "工具执行失败")
-            return AgentDecision(
-                status="failed",
-                summary="工具执行失败，已停止本轮任务。",
-                final_answer=(
-                    f"生成未成功：{err}\n\n"
-                    "请查看上方执行轨迹中的失败步骤；若是视频渲染报错，可改选「互动课件/PPT」或稍后重试。"
-                ),
-                reasoning_content=decision.reasoning_content,
-            )
-
-        required_tools = supervisor_intents.plan_required_tools(
-            goal,
-            is_profile_update_only=self._is_profile_update_only_goal(goal),
-        )
-        if (
-            required_tools == ["answer_course_question"]
-            and "answer_course_question" in available
-            and "answer_course_question" not in completed_tools
-            and "answer_course_question" not in skip_tools
-        ):
-            return self._force_tool(
-                "answer_course_question",
-                goal,
-                state,
-                decision,
-                reason="显式课程依据问答统一由可信问答内核完成",
-            )
-
-        if decision.tool_calls:
-            if decision.status == "complete":
-                decision.status = "continue"
-            decision.tool_calls = [
-                call
-                for call in decision.tool_calls
-                if call.name not in completed_tools and call.name not in skip_tools
-            ]
-            if not decision.tool_calls:
-                pending_deliverables = self._pending_deliverables(
-                    goal, available, completed_tools, skip_tools
-                )
-                if not pending_deliverables:
-                    return AgentDecision(
-                        status="complete",
-                        summary="所需交付物已全部生成。",
-                        final_answer=self._build_completion_answer(state),
-                        reasoning_content=decision.reasoning_content,
-                    )
-                tool_name = pending_deliverables[0]
-                label = supervisor_intents.deliverable_label(tool_name)
-                return self._force_tool(
-                    tool_name,
-                    goal,
-                    state,
-                    decision,
-                    reason=f"用户要求的{label}尚未生成，禁止重复调用已完成工具",
-                )
-            decision.tool_calls = self._filter_tool_calls_for_profile_only(goal, decision.tool_calls)
-            decision.tool_calls = self._align_tool_calls_with_deliverables(
-                goal,
-                completed_tools,
-                decision.tool_calls,
-                available,
-                skip_tools,
-                state,
-            )
-            for call in decision.tool_calls:
-                call.arguments = self._safe_arguments(call.name, call.arguments, goal, state)
-            if decision.tool_calls:
-                return decision
-            pending_deliverables = self._pending_deliverables(
-                goal, available, completed_tools, skip_tools
-            )
-            if pending_deliverables:
-                tool_name = pending_deliverables[0]
-                label = supervisor_intents.deliverable_label(tool_name)
-                return self._force_tool(
-                    tool_name,
-                    goal,
-                    state,
-                    decision,
-                    reason=f"用户要求的{label}尚未生成，安全约束后需补调",
-                )
-
-        pending_deliverables = self._pending_deliverables(goal, available, completed_tools, skip_tools)
-
-        hint = self._next_tool_hint(state, available, completed_tools, skip_tools)
-        if hint and decision.status == "complete":
-            return self._force_tool(hint, goal, state, decision, reason="用户指定工具")
-
-        if (
-            decision.status == "complete"
-            and self._requires_explicit_retrieval(goal, completed_tools, state, skip_tools)
-            and (
-                (
-                    "answer_course_question" in available
-                    and "answer_course_question" not in skip_tools
-                )
-                or (
-                    "search_course_knowledge" in available
-                    and "search_course_knowledge" not in skip_tools
-                )
-            )
-        ):
-            grounded_tool = (
-                "answer_course_question"
-                if required_tools == ["answer_course_question"]
-                and "answer_course_question" in available
-                and "answer_course_question" not in skip_tools
-                else "search_course_knowledge"
-            )
-            return self._force_tool(
-                grounded_tool,
-                goal,
-                state,
-                decision,
-                reason=(
-                    "用户明确要求基于课程资料回答，必须使用可信问答内核"
-                    if grounded_tool == "answer_course_question"
-                    else "生成多模态产物前必须先检索课程依据"
-                ),
-            )
-
-        if (
-            decision.status == "complete"
-            and supervisor_intents.web_search_intent(goal)
-            and "search_web" not in completed_tools
-            and "search_web" in available
-            and "search_web" not in skip_tools
-        ):
-            return self._force_tool(
-                "search_web",
-                goal,
-                state,
-                decision,
-                reason="用户要求联网搜索，必须先获取实时网页结果",
-            )
-
-        if decision.status == "complete" and pending_deliverables:
-            tool_name = pending_deliverables[0]
-            label = supervisor_intents.deliverable_label(tool_name)
-            return self._force_tool(
-                tool_name,
-                goal,
-                state,
-                decision,
-                reason=f"用户要求的{label}尚未生成，禁止仅用文字/Markdown 代替",
-            )
-
-        if decision.status == "complete" and self._has_wrong_deliverable_only(state, goal):
-            pending = self._pending_deliverables(goal, available, completed_tools, skip_tools)
-            if pending:
-                tool_name = pending[0]
-                label = supervisor_intents.deliverable_label(tool_name)
-                return self._force_tool(
-                    tool_name,
-                    goal,
-                    state,
-                    decision,
-                    reason=f"已调用错误工具，需补生成{label}",
-                )
-
-        if decision.status == "complete":
-            decision.final_answer = self._normalize_completion_answer(state, goal, decision.final_answer)
-
-        if decision.status == "complete" and self._should_use_fallback_planner(
-            goal,
-            state,
-            available,
-            completed_tools,
-            skip_tools,
-            pending_deliverables,
-        ):
-            fallback = self._fallback_next_tool(goal, available, completed_tools, skip_tools)
-            if fallback:
-                return self._force_tool(
-                    fallback,
-                    goal,
-                    state,
-                    decision,
-                    reason=f"LLM 未调用工具，安全网补调 {fallback}",
-                )
-
-        return decision
-
-    def _enforce_execution_policy(
-        self,
-        state: dict[str, Any],
-        tool_schemas: list[dict[str, Any]],
-        decision: AgentDecision,
-    ) -> AgentDecision:
-        return self._apply_safety_net(state, tool_schemas, decision)
-
-    @staticmethod
-    def _available_tool_names(tool_schemas: list[dict[str, Any]]) -> set[str]:
-        return {
-            str(item.get("function", {}).get("name"))
-            for item in tool_schemas
-            if isinstance(item, dict) and item.get("function", {}).get("name")
-        }
-
-    @staticmethod
-    def _completed_tool_names(state: dict[str, Any]) -> set[str]:
-        return {
-            str(item.get("tool_name"))
-            for item in state.get("observations") or []
-            if item.get("success") is True and item.get("tool_name")
-        }
-
-    def _pending_deliverables(
-        self,
-        goal: str,
-        available: set[str],
-        completed_tools: set[str],
-        skip_tools: set[str],
-    ) -> list[str]:
-        deliverable_set = set(self._required_deliverables(goal))
-        ordered = supervisor_intents.plan_required_tools(
-            goal,
-            is_profile_update_only=self._is_profile_update_only_goal(goal),
-        )
-        return [
-            name
-            for name in ordered
-            if name in deliverable_set
-            and name in available
-            and name not in completed_tools
-            and name not in skip_tools
-        ]
-
-    def _next_tool_hint(
-        self,
-        state: dict[str, Any],
-        available: set[str],
-        completed_tools: set[str],
-        skip_tools: set[str],
-    ) -> str | None:
-        for name in reversed(state.get("tool_hints") or []):
-            if name in available and name not in completed_tools and name not in skip_tools:
-                return str(name)
-        return None
-
-    def _requires_explicit_retrieval(
-        self,
-        goal: str,
-        completed_tools: set[str],
-        state: dict[str, Any],
-        skip_tools: set[str],
-    ) -> bool:
-        if (
-            "search_course_knowledge" in completed_tools
-            or "answer_course_question" in completed_tools
-            or "search_course_knowledge" in skip_tools
-            or "answer_course_question" in skip_tools
-        ):
-            return False
-        if state.get("citations"):
-            return False
-        explicit = ("基于课程资料", "基于资料", "给出引用", "引用来源", "课程知识库")
-        return any(phrase in goal for phrase in explicit)
-
-    def _should_use_fallback_planner(
-        self,
-        goal: str,
-        state: dict[str, Any],
-        available: set[str],
-        completed_tools: set[str],
-        skip_tools: set[str],
-        pending_deliverables: list[str],
-    ) -> bool:
-        if pending_deliverables:
-            return False
-        if int(state.get("tool_call_count") or 0) > 0:
-            return False
-        if self._is_profile_update_only_goal(goal):
-            return False
-        planned = supervisor_intents.plan_required_tools(
-            goal,
-            is_profile_update_only=False,
-        )
-        if planned == ["answer_course_question"]:
-            return False
-        return bool(self._fallback_next_tool(goal, available, completed_tools, skip_tools))
-
-    def _fallback_next_tool(
-        self,
-        goal: str,
-        available: set[str],
-        completed_tools: set[str],
-        skip_tools: set[str],
-    ) -> str | None:
-        planned = supervisor_intents.plan_required_tools(
-            goal,
-            is_profile_update_only=self._is_profile_update_only_goal(goal),
-        )
-        for name in planned:
-            if name in available and name not in completed_tools and name not in skip_tools:
-                return name
-        return None
-
-    def _force_tool(
-        self,
-        tool_name: str,
-        goal: str,
-        state: dict[str, Any],
-        decision: AgentDecision,
-        *,
-        reason: str,
-    ) -> AgentDecision:
-        return AgentDecision(
-            status="continue",
-            summary=reason,
-            plan=[f"调用 {tool_name}"],
-            tool_calls=[
-                PlannedToolCall(
-                    id=f"call_{uuid4().hex}",
-                    name=tool_name,
-                    arguments=self._safe_arguments(tool_name, {}, goal, state),
-                )
-            ],
-            reasoning_content=decision.reasoning_content,
-        )
-
-    def _filter_tool_calls_for_profile_only(
-        self,
-        goal: str,
-        tool_calls: list[PlannedToolCall],
-    ) -> list[PlannedToolCall]:
-        if not self._is_profile_update_only_goal(goal):
-            return tool_calls
-        allowed = {"update_profile_from_dialogue"}
-        return [call for call in tool_calls if call.name in allowed]
-
-    def _align_tool_calls_with_deliverables(
-        self,
-        goal: str,
-        completed_tools: set[str],
-        tool_calls: list[PlannedToolCall],
-        available: set[str],
-        skip_tools: set[str],
-        state: dict[str, Any],
-    ) -> list[PlannedToolCall]:
-        pending = self._pending_deliverables(goal, available, completed_tools, skip_tools)
-        if not pending or not tool_calls:
-            return tool_calls
-        primary = pending[0]
-        chosen = {call.name for call in tool_calls}
-        if primary in chosen:
-            return tool_calls
-        prep_tools = {"search_course_knowledge", "generate_explanation", "answer_course_question"}
-        if primary == "synthesize_speech" and chosen.issubset(prep_tools):
-            if "generate_explanation" in chosen and "generate_explanation" not in completed_tools:
-                return tool_calls
-            if supervisor_intents.should_prepare_speech_script(goal) and "generate_explanation" not in completed_tools:
-                return tool_calls
-        if chosen.isdisjoint(set(pending)):
-            return [
-                PlannedToolCall(
-                    id=f"call_{uuid4().hex}",
-                    name=primary,
-                    arguments=self._safe_arguments(primary, {}, goal, state),
-                )
-            ]
-        return tool_calls
-
-    def _deliverables_complete_decision(
-        self,
-        state: dict[str, Any],
-        tool_schemas: list[dict[str, Any]],
-    ) -> AgentDecision | None:
-        goal = str(state.get("goal") or "")
-        required = self._required_deliverables(goal)
-        if not required:
-            return None
-        available = self._available_tool_names(tool_schemas)
-        completed_tools = self._completed_tool_names(state)
-        skip_tools = set(state.get("skip_tools") or [])
-        pending = self._pending_deliverables(goal, available, completed_tools, skip_tools)
-        if pending:
-            return None
-        return AgentDecision(
-            status="complete",
-            summary="所需交付物已全部生成。",
-            final_answer=self._build_completion_answer(state),
-        )
-
-    def _build_completion_answer(self, state: dict[str, Any]) -> str:
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
-
-    def _build_search_results_answer(self, state: dict[str, Any], goal: str) -> str | None:
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
-
-    @staticmethod
-    def _format_search_output_answer(tool_name: str, output: dict[str, Any], goal: str) -> str:
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
-
-    def _profile_update_only_decision(
-        self,
-        state: dict[str, Any],
-        tool_schemas: list[dict[str, Any]],
-    ) -> AgentDecision | None:
-        goal = str(state.get("goal") or "")
-        if not self._is_profile_update_only_goal(goal):
-            return None
-        available = {
-            str(item.get("function", {}).get("name"))
-            for item in tool_schemas
-            if isinstance(item, dict)
-        }
-        if "update_profile_from_dialogue" not in available:
-            return None
-        completed = any(
-            item.get("success") is True and item.get("tool_name") == "update_profile_from_dialogue"
-            for item in state.get("observations") or []
-        )
-        if completed:
-            return AgentDecision(
-                status="complete",
-                summary="对话式学习画像已更新。",
-                final_answer="已记录你的学习目标、偏好和薄弱点，后续学习建议会参考这些信息。",
-            )
-        return AgentDecision(
-            status="continue",
-            summary="本轮仅更新对话式学习画像，不扩张为资源或练习生成任务。",
-            plan=["从当前对话提取并更新学习画像"],
-            tool_calls=[
-                PlannedToolCall(
-                    id=f"call_{uuid4().hex}",
-                    name="update_profile_from_dialogue",
-                    arguments=self._safe_arguments("update_profile_from_dialogue", {}, goal, state),
-                )
-            ],
-        )
-
-    def _intent_first_decision(
-        self,
-        state: dict[str, Any],
-        tool_schemas: list[dict[str, Any]],
-    ) -> AgentDecision | None:
-        if int(state.get("tool_call_count") or 0) > 0:
-            return None
-        goal = str(state.get("goal") or "")
-        if not supervisor_intents.should_intent_first_route(goal):
-            return None
-        available = self._available_tool_names(tool_schemas)
-        skip_tools = set(state.get("skip_tools") or [])
-        planned = self._required_tools(goal)
-        if not planned:
-            return None
-        calls: list[PlannedToolCall] = []
-        for name in planned:
-            if name not in available or name in skip_tools:
-                continue
-            calls.append(
-                PlannedToolCall(
-                    id=f"call_{uuid4().hex}",
-                    name=name,
-                    arguments=self._safe_arguments(name, {}, goal, state),
-                )
-            )
-        if not calls:
-            return None
-        primary = calls[-1].name
-        return AgentDecision(
-            status="continue",
-            summary=f"意图识别：优先调用 {supervisor_intents.deliverable_label(primary)}",
-            plan=[f"调用 {item.name}" for item in calls],
-            tool_calls=calls,
-        )
-
-    @staticmethod
-    def _has_wrong_deliverable_only(state: dict[str, Any], goal: str) -> bool:
-        required = set(supervisor_intents.required_deliverables(goal))
-        if not required:
-            return False
-        completed = {
-            str(item.get("tool_name"))
-            for item in state.get("observations") or []
-            if item.get("success") is True and item.get("tool_name")
-        }
-        if required & completed:
-            return False
-        generation = {
-            "generate_lesson_video",
-            "generate_immersive_classroom",
-            "generate_interactive_courseware",
-            "generate_storyboard_html",
-            "generate_educational_image",
-            "generate_diagram",
-            "generate_mindmap",
-            "generate_explanation",
-            "synthesize_speech",
-        }
-        return bool(completed & generation)
-
-    def _normalize_completion_answer(
-        self,
-        state: dict[str, Any],
-        goal: str,
-        answer: str,
-    ) -> str:
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
-
-    def _is_profile_update_only_goal(self, goal: str) -> bool:
-        return supervisor_intents.is_profile_update_only_goal(goal)
-
-    def _required_tools(self, goal: str) -> list[str]:
-        tools = supervisor_intents.plan_required_tools(
-            goal,
-            is_profile_update_only=self._is_profile_update_only_goal(goal),
-        )
-        return self._ensure_knowledge_search_first(goal, tools)
-
-    def _required_deliverables(self, goal: str) -> list[str]:
-        return supervisor_intents.required_deliverables(goal)
-
-    def _speech_intent(self, goal: str) -> bool:
-        return supervisor_intents.speech_intent(goal)
-
-    def _video_intent(self, goal: str) -> bool:
-        return supervisor_intents.video_intent(goal)
-
-    def _extract_topic_from_goal(self, goal: str) -> str:
-        return supervisor_intents.extract_topic_from_segment(goal)
-
-    def _topic_for_tool(self, tool_name: str, goal: str, state: dict[str, Any]) -> str:
-        tool_topics = state.get("tool_topics") or {}
-        topic = str(tool_topics.get(tool_name) or "").strip()
-        if topic:
-            return topic
-        return self._extract_topic_from_goal(goal)
-
-    def _resolve_speech_text(self, state: dict[str, Any], goal: str, text: str | None = None) -> str:
-        candidate = str(text or "").strip()
-        if candidate and candidate != goal.strip() and len(candidate) >= 40:
-            return candidate[:4000]
-        for obs in reversed(state.get("observations") or []):
-            output = obs.get("output")
-            if not isinstance(output, dict):
-                continue
-            for key in ("content", "text", "answer", "summary"):
-                value = output.get(key)
-                if isinstance(value, str) and len(value.strip()) >= 40:
-                    return value.strip()[:4000]
-            chunks = output.get("chunks")
-            if isinstance(chunks, list) and chunks:
-                merged = "\n".join(
-                    str(item.get("content") or item.get("text") or item)
-                    for item in chunks[:5]
-                    if item is not None
-                ).strip()
-                if len(merged) >= 40:
-                    return merged[:4000]
-        topic = self._extract_topic_from_goal(goal)
-        return (
-            f"你好，下面为你讲解{topic}。"
-            f"{topic}是数据结构中的核心知识点，遵循先进先出的原则。"
-            f"常见操作包括入队、出队、取队头和判空，在任务调度与广度优先搜索中应用广泛。"
-        )[:4000]
-
-    _GENERATION_TOOLS = {
-        "generate_learning_path",
-        "generate_explanation",
-        "generate_quiz",
-        "generate_mindmap",
-        "generate_diagram",
-        "generate_educational_image",
-        "generate_lesson_video",
-        "generate_immersive_classroom",
-        "generate_storyboard_html",
-        "generate_interactive_courseware",
-        "answer_course_question",
-    }
-
-    def _ensure_knowledge_search_first(self, goal: str, tools: list[str]) -> list[str]:
-        if self._is_profile_update_only_goal(goal):
-            return tools
-        needs_grounding = any(name in self._GENERATION_TOOLS for name in tools) or self._should_ground_in_course_materials(goal)
-        if needs_grounding and "search_course_knowledge" not in tools:
-            return ["search_course_knowledge", *tools]
-        return tools
-
-    def _should_ground_in_course_materials(self, goal: str) -> bool:
-        keywords = (
-            "什么是",
-            "讲解",
-            "解释",
-            "为什么",
-            "如何",
-            "帮我",
-            "BFS",
-            "DFS",
-            "广度优先",
-            "深度优先",
-            "排序",
-            "队列",
-            "栈",
-            "二叉树",
-            "图",
-            "遍历",
-            "算法",
-            "数据结构",
-            "哈希",
-            "链表",
-        )
-        return any(keyword in goal for keyword in keywords)
-
-    def _safe_arguments(
-        self,
-        tool_name: str,
-        arguments: dict[str, Any],
-        goal: str,
-        state: dict[str, Any] | None = None,
-    ) -> dict[str, Any]:
-        normalized = dict(arguments)
-        state = state or {}
-        topic = self._topic_for_tool(tool_name, goal, state)
-        defaults: dict[str, dict[str, Any]] = {
-            "search_course_knowledge": {"query": topic or goal, "top_k": 10},
-            "search_web": {"query": topic or goal, "max_results": 5},
-            "answer_course_question": {"question": goal, "top_k": 5},
-            "generate_learning_path": {"goal": topic or goal},
-            "generate_explanation": {"topic": topic, "requirement": goal},
-            "generate_quiz": {"topic": topic},
-            "parse_uploaded_document": {},
-            "generate_mindmap": {"topic": topic, "scope": "course", "depth": 3},
-            "generate_diagram": {"concept": topic, "diagram_type": "flowchart"},
-            "generate_educational_image": {
-                "topic": topic,
-                "image_type": "concept_illustration",
-                "style": "clean educational illustration",
-                "size": "1280x720",
-                "requirement": goal,
-            },
-            "generate_lesson_video": {
-                "topic": topic,
-                "duration_seconds": 90,
-                "visual_mode": "storyboard",
-                "target_level": "undergraduate",
-            },
-            "generate_immersive_classroom": {
-                "topic": topic,
-                "learning_goal": topic or goal,
-                "generate_video_export": True,
-                "enable_images": True,
-                "enable_video_clips": False,
-                "enable_tts": True,
-            },
-            "generate_storyboard_html": {
-                "topic": topic,
-                "duration_seconds": 90,
-                "requirement": goal,
-            },
-            "generate_interactive_courseware": {
-                "topic": topic,
-                "interaction_type": "stepper",
-                "target_level": "undergraduate",
-                "requirement": goal,
-            },
-            "transcribe_audio": {},
-            "synthesize_speech": {
-                "text": self._resolve_speech_text(state, goal),
-                "model_type": "tts",
-                "response_format": "wav",
-            },
-            "update_profile_from_dialogue": {"dialogue_text": goal},
-            "review_artifacts": {"content": goal},
-            "review_multimodal_asset": {},
-        }
-        for key, value in defaults.get(tool_name, {}).items():
-            if not normalized.get(key):
-                normalized[key] = value
-        if tool_name == "review_multimodal_asset" and not normalized.get("asset_id"):
-            import re
-
-            match = re.search(
-                r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
-                goal,
-                flags=re.IGNORECASE,
-            )
-            if match:
-                normalized["asset_id"] = match.group(0)
-        if tool_name == "generate_quiz" and normalized.get("question_types"):
-            aliases = {
-                "选择题": "single_choice",
-                "单选题": "single_choice",
-                "多选题": "multiple_choice",
-                "判断题": "judge",
-                "简答题": "short_answer",
-                "填空题": "fill_blank",
-                "fill_in_blank": "fill_blank",
-                "编程题": "coding",
-            }
-            allowed = {
-                "single_choice",
-                "multiple_choice",
-                "judge",
-                "short_answer",
-                "fill_blank",
-                "coding",
-            }
-            normalized["question_types"] = [
-                aliases.get(str(item), str(item))
-                for item in normalized["question_types"]
-                if aliases.get(str(item), str(item)) in allowed
-            ] or ["single_choice"]
-        return normalized
+        answer = extract_final_answer_text(content)
+        return AgentDecision(status="complete", summary="Supervisor 直接完成回答。", final_answer=answer) if answer else AgentDecision(status="failed", summary="Supervisor 未返回可执行决策。", final_answer="智能体未能生成有效计划，请补充目标后重试。")
 
     def _normalize_decision_payload(self, data: dict[str, Any]) -> dict[str, Any]:
-        normalized = dict(data)
-        calls: list[dict[str, Any]] = []
+        normalized = dict(data); calls = []
         for item in data.get("tool_calls") or []:
-            if not isinstance(item, dict):
-                continue
-            name = item.get("name") or item.get("tool_name") or item.get("tool")
-            if not name:
-                continue
-            calls.append(
-                {
-                    "id": str(item.get("id") or f"call_{uuid4().hex}"),
-                    "name": str(name),
-                    "arguments": dict(
-                        item.get("arguments") or item.get("parameters") or item.get("args") or {}
-                    ),
-                }
-            )
+            if isinstance(item, dict) and (name := item.get("name") or item.get("tool_name") or item.get("tool")):
+                calls.append({"id": str(item.get("id") or f"call_{uuid4().hex}"), "name": str(name), "arguments": dict(item.get("arguments") or item.get("parameters") or item.get("args") or {})})
         normalized["tool_calls"] = calls
-        if not normalized.get("plan") and normalized.get("summary"):
-            normalized["plan"] = [str(normalized["summary"])]
+        if not normalized.get("plan") and normalized.get("summary"): normalized["plan"] = [str(normalized["summary"])]
         return normalized
 
-    def _build_messages(self, state: dict[str, Any]) -> list[ChatMessage]:
-        system = (
-            "你是智学工坊 Supervisor Agent。你的职责是根据用户目标、历史消息和工具观察，"
-            "**直接通过原生 function calling 选择下一步工具**。"
-            "优先调用有来源的知识检索工具；工具失败后调整方案，不要重复无效调用。"
-            "交付物必须与用户意图一致：语音→synthesize_speech，普通短视频→generate_lesson_video，"
-            "沉浸课堂/一键课程→generate_immersive_classroom，"
-            "PPT/幻灯片/课件/slides/deck/keynote/网页ppt→generate_interactive_courseware（多页 HTML 互动课件，不是视频），"
-            "插图→generate_educational_image，流程图→generate_diagram，思维导图→generate_mindmap，练习→generate_quiz，"
-            "纯答疑→answer_course_question，文字讲解资源→generate_explanation。"
-            "用户一句话包含多个交付物（如「二叉树 ppt 和队列思维导图」）时，必须分别调用对应工具，"
-            "每个工具的 topic/concept 只用该子任务的主题词，不要把整句当 topic。"
-            "用户说「讲解 ppt / 做一份幻灯片 / 课件」时，禁止调用 generate_lesson_video。"
-            "禁止把文字资源、Markdown 或摘要冒充语音/视频/图片结果。"
-            "当用户要求语音时，先准备讲解文本（检索/生成），再 synthesize_speech。"
-            "当用户要求插图/知识卡片时：有文生图 API 则 generate_educational_image；"
-            "无 API 时同一工具会自动产出简明 Mermaid 知识卡片（思维导图或流程图）。"
-            "Mermaid 与文生图均应保持节点/元素简明，复杂知识用多层而非单节点堆字。"
-            "只有在任务真正完成、且不需要再调用工具时，才返回纯文本 final_answer。"
-            "若仍需工具，请直接发起 tool call，不要只返回 JSON 计划。"
-            "不要输出隐式思维链，只输出简洁决策摘要。"
-        )
-        goal = str(state.get("goal") or "")
-        recommended = supervisor_intents.plan_required_tools(
-            goal,
-            is_profile_update_only=self._is_profile_update_only_goal(goal),
-        )
-        context = {
-            "goal": state.get("goal"),
-            "recommended_tools": recommended,
-            "recommended_tool_labels": [
-                supervisor_intents.deliverable_label(name) for name in recommended
-            ],
-            "tool_topics": state.get("tool_topics") or supervisor_intents.parse_tool_topics(goal),
-            "parsed_intents": state.get("parsed_intents")
-            or [
-                {"segment": item.segment, "topic": item.topic, "tools": list(item.tools)}
-                for item in supervisor_intents.parse_goal_intents(goal)
-            ],
-            "current_plan": state.get("current_plan") or [],
-            "observations": (state.get("observations") or [])[-8:],
-            "artifacts": state.get("artifacts") or [],
-            "learning_context": state.get("context") or {},
-            "iteration_count": state.get("iteration_count") or 0,
-        }
-        messages = [ChatMessage(role="system", content=system)]
-        for item in (state.get("messages") or [])[-12:]:
-            messages.append(
-                ChatMessage(
-                    role=str(item.get("role") or "user"),
-                    content=str(item.get("content") or ""),
-                )
-            )
-        prior_tool_calls = state.get("tool_calls") or []
-        observations = state.get("observations") or []
-        reasoning_content = state.get("protocol_reasoning_content")
-        if reasoning_content and prior_tool_calls and observations:
-            last_call = prior_tool_calls[-1]
-            messages.append(
-                ChatMessage(
-                    role="assistant",
-                    content="",
-                    reasoning_content=str(reasoning_content),
-                    tool_calls=[
-                        ToolCall(
-                            id=str(last_call.get("id") or ""),
-                            name=str(last_call.get("name") or ""),
-                            arguments=dict(last_call.get("arguments") or {}),
-                        )
-                    ],
-                )
-            )
-            messages.append(
-                ChatMessage(
-                    role="tool",
-                    tool_call_id=str(last_call.get("id") or ""),
-                    content=json.dumps(observations[-1], ensure_ascii=False),
-                )
-            )
-        messages.append(
-            ChatMessage(
-                role="user",
-                content=f"当前任务状态：{json.dumps(context, ensure_ascii=False)}",
-            )
-        )
-        return messages
+    def _apply_safety_net(self, state: dict[str, Any], schemas: list[dict[str, Any]], decision: AgentDecision) -> AgentDecision: return apply_safety_net(self._policy, state, schemas, decision)
+    def _enforce_execution_policy(self, state: dict[str, Any], schemas: list[dict[str, Any]], decision: AgentDecision) -> AgentDecision: return self._apply_safety_net(state, schemas, decision)
+    def _available_tool_names(self, schemas: list[dict[str, Any]]) -> set[str]: return self._policy.available_tool_names(schemas)
+    def _completed_tool_names(self, state: dict[str, Any]) -> set[str]: return self._policy.completed_tool_names(state)
+    def _pending_deliverables(self, goal: str, available: set[str], completed: set[str], skip: set[str]) -> list[str]: return self._policy.pending_deliverables(goal, available, completed, skip)
+    def _next_tool_hint(self, state: dict[str, Any], available: set[str], completed: set[str], skip: set[str]) -> str | None: return self._policy.next_tool_hint(state, available, completed, skip)
+    def _requires_explicit_retrieval(self, goal: str, completed: set[str], state: dict[str, Any], skip: set[str]) -> bool: return self._policy.requires_explicit_retrieval(goal, completed, state, skip)
+    def _should_use_fallback_planner(self, goal: str, state: dict[str, Any], available: set[str], completed: set[str], skip: set[str], pending: list[str]) -> bool: return self._policy.should_use_fallback_planner(goal, state, available, completed, skip, pending)
+    def _fallback_next_tool(self, goal: str, available: set[str], completed: set[str], skip: set[str]) -> str | None: return self._policy.fallback_next_tool(goal, available, completed, skip)
+    def _force_tool(self, name: str, goal: str, state: dict[str, Any], decision: AgentDecision, *, reason: str) -> AgentDecision: return self._policy.force_tool(name, goal, state, decision, reason=reason)
+    def _filter_tool_calls_for_profile_only(self, goal: str, calls: list[PlannedToolCall]) -> list[PlannedToolCall]: return self._policy.filter_tool_calls_for_profile_only(goal, calls)
+    def _align_tool_calls_with_deliverables(self, goal: str, completed: set[str], calls: list[PlannedToolCall], available: set[str], skip: set[str], state: dict[str, Any]) -> list[PlannedToolCall]: return self._policy.align_tool_calls_with_deliverables(goal, completed, calls, available, skip, state)
+    def _deliverables_complete_decision(self, state: dict[str, Any], schemas: list[dict[str, Any]]) -> AgentDecision | None: return self._policy.deliverables_complete_decision(state, schemas)
+    def _profile_update_only_decision(self, state: dict[str, Any], schemas: list[dict[str, Any]]) -> AgentDecision | None: return self._policy.profile_update_only_decision(state, schemas)
+    def _intent_first_decision(self, state: dict[str, Any], schemas: list[dict[str, Any]]) -> AgentDecision | None: return self._policy.intent_first_decision(state, schemas)
+    def _has_wrong_deliverable_only(self, state: dict[str, Any], goal: str) -> bool: return self._policy.has_wrong_deliverable_only(state, goal)
+    def _normalize_completion_answer(self, state: dict[str, Any], goal: str, answer: str) -> str: return normalize_completion_answer(state, goal, answer)
+    def _build_completion_answer(self, state: dict[str, Any]) -> str: return build_completion_answer(state)
+    def _build_search_results_answer(self, state: dict[str, Any], goal: str) -> str | None: return build_search_results_answer(state, goal)
+    @staticmethod
+    def _format_search_output_answer(name: str, output: dict[str, Any], goal: str) -> str: return format_search_output_answer(name, output, goal)
+    def _is_profile_update_only_goal(self, goal: str) -> bool: return self._policy.is_profile_update_only_goal(goal)
+    def _required_tools(self, goal: str) -> list[str]: return self._policy.required_tools(goal)
+    def _required_deliverables(self, goal: str) -> list[str]: return self._policy.required_deliverables(goal)
+    def _speech_intent(self, goal: str) -> bool: return supervisor_intents.speech_intent(goal)
+    def _video_intent(self, goal: str) -> bool: return supervisor_intents.video_intent(goal)
+    def _extract_topic_from_goal(self, goal: str) -> str: return supervisor_intents.extract_topic_from_segment(goal)
+    def _topic_for_tool(self, name: str, goal: str, state: dict[str, Any]) -> str: return _topic_for_tool(name, goal, state)
+    def _resolve_speech_text(self, state: dict[str, Any], goal: str, text: str | None = None) -> str: return _resolve_speech_text(state, goal, text)
+    def _safe_arguments(self, name: str, args: dict[str, Any], goal: str, state: dict[str, Any] | None = None) -> dict[str, Any]: return safe_arguments(name, args, goal, state)
+    def _build_messages(self, state: dict[str, Any]) -> list[ChatMessage]: return build_messages(state)
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
index 0000000..51b2f4d
--- /dev/null
+++ b/backend/app/agent_runtime/supervisor_policy.py
@@ -0,0 +1,290 @@
+from __future__ import annotations
+
+import re
+from typing import Any
+
+from app.agent_runtime import supervisor_intents
+from app.agent_runtime.state import AgentDecision, PlannedToolCall
+from app.agent_runtime.supervisor_completion import build_completion_answer, normalize_completion_answer
+from uuid import uuid4
+
+
+def _topic_for_tool(tool_name: str, goal: str, state: dict[str, Any]) -> str:
+    tool_topics = state.get("tool_topics") or {}
+    topic = str(tool_topics.get(tool_name) or "").strip()
+    return topic or supervisor_intents.extract_topic_from_segment(goal)
+
+
+def _resolve_speech_text(state: dict[str, Any], goal: str, text: str | None = None) -> str:
+    candidate = str(text or "").strip()
+    if candidate and candidate != goal.strip() and len(candidate) >= 40:
+        return candidate[:4000]
+    for observation in reversed(state.get("observations") or []):
+        output = observation.get("output")
+        if not isinstance(output, dict):
+            continue
+        for key in ("content", "text", "answer", "summary"):
+            value = output.get(key)
+            if isinstance(value, str) and len(value.strip()) >= 40:
+                return value.strip()[:4000]
+        chunks = output.get("chunks")
+        if isinstance(chunks, list) and chunks:
+            merged = "\n".join(str(item.get("content") or item.get("text") or item) for item in chunks[:5] if item is not None).strip()
+            if len(merged) >= 40:
+                return merged[:4000]
+    topic = supervisor_intents.extract_topic_from_segment(goal)
+    return f"你好，下面为你讲解{topic}。{topic}是数据结构中的核心知识点，遵循先进先出的原则。常见操作包括入队、出队、取队头和判空，在任务调度与广度优先搜索中应用广泛。"[:4000]
+
+
+def safe_arguments(
+    tool_name: str,
+    arguments: dict[str, Any],
+    goal: str,
+    state: dict[str, Any] | None = None,
+) -> dict[str, Any]:
+    normalized = dict(arguments)
+    state = state or {}
+    topic = _topic_for_tool(tool_name, goal, state)
+    defaults: dict[str, dict[str, Any]] = {
+        "search_course_knowledge": {"query": topic or goal, "top_k": 10},
+        "search_web": {"query": topic or goal, "max_results": 5},
+        "answer_course_question": {"question": goal, "top_k": 5},
+        "generate_learning_path": {"goal": topic or goal}, "generate_explanation": {"topic": topic, "requirement": goal},
+        "generate_quiz": {"topic": topic}, "parse_uploaded_document": {},
+        "generate_mindmap": {"topic": topic, "scope": "course", "depth": 3},
+        "generate_diagram": {"concept": topic, "diagram_type": "flowchart"},
+        "generate_educational_image": {"topic": topic, "image_type": "concept_illustration", "style": "clean educational illustration", "size": "1280x720", "requirement": goal},
+        "generate_lesson_video": {"topic": topic, "duration_seconds": 90, "visual_mode": "storyboard", "target_level": "undergraduate"},
+        "generate_immersive_classroom": {"topic": topic, "learning_goal": topic or goal, "generate_video_export": True, "enable_images": True, "enable_video_clips": False, "enable_tts": True},
+        "generate_storyboard_html": {"topic": topic, "duration_seconds": 90, "requirement": goal},
+        "generate_interactive_courseware": {"topic": topic, "interaction_type": "stepper", "target_level": "undergraduate", "requirement": goal},
+        "transcribe_audio": {}, "synthesize_speech": {"text": _resolve_speech_text(state, goal), "model_type": "tts", "response_format": "wav"},
+        "update_profile_from_dialogue": {"dialogue_text": goal}, "review_artifacts": {"content": goal}, "review_multimodal_asset": {},
+    }
+    for key, value in defaults.get(tool_name, {}).items():
+        if not normalized.get(key):
+            normalized[key] = value
+    if tool_name == "review_multimodal_asset" and not normalized.get("asset_id"):
+        match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", goal, flags=re.IGNORECASE)
+        if match:
+            normalized["asset_id"] = match.group(0)
+    if tool_name == "generate_quiz" and normalized.get("question_types"):
+        aliases = {"选择题": "single_choice", "单选题": "single_choice", "多选题": "multiple_choice", "判断题": "judge", "简答题": "short_answer", "填空题": "fill_blank", "fill_in_blank": "fill_blank", "编程题": "coding"}
+        allowed = {"single_choice", "multiple_choice", "judge", "short_answer", "fill_blank", "coding"}
+        normalized["question_types"] = [aliases.get(str(item), str(item)) for item in normalized["question_types"] if aliases.get(str(item), str(item)) in allowed] or ["single_choice"]
+    return normalized
+
+
+class SupervisorPolicy:
+    _GENERATION_TOOLS = {"generate_learning_path", "generate_explanation", "generate_quiz", "generate_mindmap", "generate_diagram", "generate_educational_image", "generate_lesson_video", "generate_immersive_classroom", "generate_storyboard_html", "generate_interactive_courseware", "answer_course_question"}
+
+    @staticmethod
+    def available_tool_names(tool_schemas: list[dict[str, Any]]) -> set[str]:
+        return {str(item.get("function", {}).get("name")) for item in tool_schemas if isinstance(item, dict) and item.get("function", {}).get("name")}
+
+    @staticmethod
+    def completed_tool_names(state: dict[str, Any]) -> set[str]:
+        return {str(item.get("tool_name")) for item in state.get("observations") or [] if item.get("success") is True and item.get("tool_name")}
+
+    @staticmethod
+    def is_profile_update_only_goal(goal: str) -> bool:
+        return supervisor_intents.is_profile_update_only_goal(goal)
+
+    def required_deliverables(self, goal: str) -> list[str]:
+        return supervisor_intents.required_deliverables(goal)
+
+    def required_tools(self, goal: str) -> list[str]:
+        tools = supervisor_intents.plan_required_tools(goal, is_profile_update_only=self.is_profile_update_only_goal(goal))
+        if self.is_profile_update_only_goal(goal):
+            return tools
+        needs_grounding = any(name in self._GENERATION_TOOLS for name in tools) or self.should_ground_in_course_materials(goal)
+        return ["search_course_knowledge", *tools] if needs_grounding and "search_course_knowledge" not in tools else tools
+
+    def pending_deliverables(self, goal: str, available: set[str], completed_tools: set[str], skip_tools: set[str]) -> list[str]:
+        deliverable_set = set(self.required_deliverables(goal))
+        ordered = supervisor_intents.plan_required_tools(goal, is_profile_update_only=self.is_profile_update_only_goal(goal))
+        return [name for name in ordered if name in deliverable_set and name in available and name not in completed_tools and name not in skip_tools]
+
+    @staticmethod
+    def next_tool_hint(state: dict[str, Any], available: set[str], completed_tools: set[str], skip_tools: set[str]) -> str | None:
+        return next((str(name) for name in reversed(state.get("tool_hints") or []) if name in available and name not in completed_tools and name not in skip_tools), None)
+
+    @staticmethod
+    def requires_explicit_retrieval(goal: str, completed_tools: set[str], state: dict[str, Any], skip_tools: set[str]) -> bool:
+        if {"search_course_knowledge", "answer_course_question"} & (completed_tools | skip_tools) or state.get("citations"):
+            return False
+        return any(phrase in goal for phrase in ("基于课程资料", "基于资料", "给出引用", "引用来源", "课程知识库"))
+
+    def fallback_next_tool(self, goal: str, available: set[str], completed_tools: set[str], skip_tools: set[str]) -> str | None:
+        return next((name for name in self.required_tools(goal) if name in available and name not in completed_tools and name not in skip_tools), None)
+
+    def should_use_fallback_planner(self, goal: str, state: dict[str, Any], available: set[str], completed_tools: set[str], skip_tools: set[str], pending: list[str]) -> bool:
+        if pending or int(state.get("tool_call_count") or 0) > 0 or self.is_profile_update_only_goal(goal):
+            return False
+        return supervisor_intents.plan_required_tools(goal, is_profile_update_only=False) != ["answer_course_question"] and bool(self.fallback_next_tool(goal, available, completed_tools, skip_tools))
+
+    def force_tool(self, tool_name: str, goal: str, state: dict[str, Any], decision: AgentDecision, *, reason: str) -> AgentDecision:
+        return AgentDecision(status="continue", summary=reason, plan=[f"调用 {tool_name}"], tool_calls=[PlannedToolCall(id=f"call_{uuid4().hex}", name=tool_name, arguments=safe_arguments(tool_name, {}, goal, state))], reasoning_content=decision.reasoning_content)
+
+    def filter_tool_calls_for_profile_only(self, goal: str, calls: list[PlannedToolCall]) -> list[PlannedToolCall]:
+        return [call for call in calls if call.name == "update_profile_from_dialogue"] if self.is_profile_update_only_goal(goal) else calls
+
+    def align_tool_calls_with_deliverables(self, goal: str, completed: set[str], calls: list[PlannedToolCall], available: set[str], skip: set[str], state: dict[str, Any]) -> list[PlannedToolCall]:
+        pending = self.pending_deliverables(goal, available, completed, skip)
+        if not pending or not calls or pending[0] in {call.name for call in calls}:
+            return calls
+        chosen = {call.name for call in calls}
+        prep = {"search_course_knowledge", "generate_explanation", "answer_course_question"}
+        if pending[0] == "synthesize_speech" and chosen.issubset(prep) and ("generate_explanation" in chosen and "generate_explanation" not in completed or supervisor_intents.should_prepare_speech_script(goal) and "generate_explanation" not in completed):
+            return calls
+        return [PlannedToolCall(id=f"call_{uuid4().hex}", name=pending[0], arguments=safe_arguments(pending[0], {}, goal, state))] if chosen.isdisjoint(set(pending)) else calls
+
+    def deliverables_complete_decision(self, state: dict[str, Any], schemas: list[dict[str, Any]]) -> AgentDecision | None:
+        goal = str(state.get("goal") or "")
+        if not self.required_deliverables(goal):
+            return None
+        if self.pending_deliverables(goal, self.available_tool_names(schemas), self.completed_tool_names(state), set(state.get("skip_tools") or [])):
+            return None
+        return AgentDecision(status="complete", summary="所需交付物已全部生成。", final_answer=build_completion_answer(state))
+
+    def profile_update_only_decision(self, state: dict[str, Any], schemas: list[dict[str, Any]]) -> AgentDecision | None:
+        goal = str(state.get("goal") or "")
+        if not self.is_profile_update_only_goal(goal) or "update_profile_from_dialogue" not in self.available_tool_names(schemas):
+            return None
+        if "update_profile_from_dialogue" in self.completed_tool_names(state):
+            return AgentDecision(status="complete", summary="对话式学习画像已更新。", final_answer="已记录你的学习目标、偏好和薄弱点，后续学习建议会参考这些信息。")
+        return AgentDecision(status="continue", summary="本轮仅更新对话式学习画像，不扩张为资源或练习生成任务。", plan=["从当前对话提取并更新学习画像"], tool_calls=[PlannedToolCall(id=f"call_{uuid4().hex}", name="update_profile_from_dialogue", arguments=safe_arguments("update_profile_from_dialogue", {}, goal, state))])
+
+    def intent_first_decision(self, state: dict[str, Any], schemas: list[dict[str, Any]]) -> AgentDecision | None:
+        goal = str(state.get("goal") or "")
+        if int(state.get("tool_call_count") or 0) > 0 or not supervisor_intents.should_intent_first_route(goal):
+            return None
+        available, skip = self.available_tool_names(schemas), set(state.get("skip_tools") or [])
+        calls = [PlannedToolCall(id=f"call_{uuid4().hex}", name=name, arguments=safe_arguments(name, {}, goal, state)) for name in self.required_tools(goal) if name in available and name not in skip]
+        return AgentDecision(status="continue", summary=f"意图识别：优先调用 {supervisor_intents.deliverable_label(calls[-1].name)}", plan=[f"调用 {item.name}" for item in calls], tool_calls=calls) if calls else None
+
+    @staticmethod
+    def has_wrong_deliverable_only(state: dict[str, Any], goal: str) -> bool:
+        required = set(supervisor_intents.required_deliverables(goal))
+        completed = {str(item.get("tool_name")) for item in state.get("observations") or [] if item.get("success") is True and item.get("tool_name")}
+        generation = {"generate_lesson_video", "generate_immersive_classroom", "generate_interactive_courseware", "generate_storyboard_html", "generate_educational_image", "generate_diagram", "generate_mindmap", "generate_explanation", "synthesize_speech"}
+        return bool(required) and not bool(required & completed) and bool(completed & generation)
+
+    @staticmethod
+    def should_ground_in_course_materials(goal: str) -> bool:
+        return any(keyword in goal for keyword in ("什么是", "讲解", "解释", "为什么", "如何", "帮我", "BFS", "DFS", "广度优先", "深度优先", "排序", "队列", "栈", "二叉树", "图", "遍历", "算法", "数据结构", "哈希", "链表"))
+
+
+def apply_safety_net(
+    host: SupervisorPolicy,
+    state: dict[str, Any],
+    tool_schemas: list[dict[str, Any]],
+    decision: AgentDecision,
+) -> AgentDecision:
+    """Apply the deterministic safety boundary around an LLM decision."""
+    goal = str(state.get("goal") or "")
+    available = host.available_tool_names(tool_schemas)
+    completed_tools = host.completed_tool_names(state)
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
+        goal, is_profile_update_only=host.is_profile_update_only_goal(goal)
+    )
+    if required_tools == ["answer_course_question"] and "answer_course_question" in available and "answer_course_question" not in completed_tools and "answer_course_question" not in skip_tools:
+        return host.force_tool("answer_course_question", goal, state, decision, reason="显式课程依据问答统一由可信问答内核完成")
+
+    if decision.tool_calls:
+        requested_calls = list(decision.tool_calls)
+        all_calls_rejected_as_non_candidates = all(
+            call.name not in available for call in requested_calls
+        )
+        if decision.status == "complete":
+            decision.status = "continue"
+        decision.tool_calls = [
+            call for call in decision.tool_calls
+            if call.name in available
+            and call.name not in completed_tools
+            and call.name not in skip_tools
+        ]
+        if not decision.tool_calls:
+            if all_calls_rejected_as_non_candidates:
+                safe_tool = host.next_tool_hint(state, available, completed_tools, skip_tools)
+                safe_tool = safe_tool or host.fallback_next_tool(
+                    goal, available, completed_tools, skip_tools
+                )
+                safe_tool = safe_tool or next(
+                    (
+                        str(item.get("function", {}).get("name"))
+                        for item in tool_schemas
+                        if str(item.get("function", {}).get("name")) in available
+                        and str(item.get("function", {}).get("name")) not in completed_tools
+                        and str(item.get("function", {}).get("name")) not in skip_tools
+                    ),
+                    None,
+                )
+                if safe_tool:
+                    return host.force_tool(
+                        safe_tool,
+                        goal,
+                        state,
+                        decision,
+                        reason="模型请求了非候选工具，安全网改用允许的候选工具",
+                    )
+                return AgentDecision(
+                    status="replan",
+                    summary="模型请求了当前任务不允许的工具，需要基于候选工具重新规划。",
+                    plan=["仅根据当前候选工具重新规划下一步"],
+                    reasoning_content=decision.reasoning_content,
+                )
+            pending = host.pending_deliverables(goal, available, completed_tools, skip_tools)
+            if not pending:
+                return AgentDecision(status="complete", summary="所需交付物已全部生成。", final_answer=build_completion_answer(state), reasoning_content=decision.reasoning_content)
+            tool_name = pending[0]
+            return host.force_tool(tool_name, goal, state, decision, reason=f"用户要求的{supervisor_intents.deliverable_label(tool_name)}尚未生成，禁止重复调用已完成工具")
+        decision.tool_calls = host.filter_tool_calls_for_profile_only(goal, decision.tool_calls)
+        decision.tool_calls = host.align_tool_calls_with_deliverables(goal, completed_tools, decision.tool_calls, available, skip_tools, state)
+        for call in decision.tool_calls:
+            call.arguments = safe_arguments(call.name, call.arguments, goal, state)
+        if decision.tool_calls:
+            return decision
+        pending = host.pending_deliverables(goal, available, completed_tools, skip_tools)
+        if pending:
+            tool_name = pending[0]
+            return host.force_tool(tool_name, goal, state, decision, reason=f"用户要求的{supervisor_intents.deliverable_label(tool_name)}尚未生成，安全约束后需补调")
+
+    pending = host.pending_deliverables(goal, available, completed_tools, skip_tools)
+    hint = host.next_tool_hint(state, available, completed_tools, skip_tools)
+    if hint and decision.status == "complete":
+        return host.force_tool(hint, goal, state, decision, reason="用户指定工具")
+    if decision.status == "complete" and host.requires_explicit_retrieval(goal, completed_tools, state, skip_tools) and (("answer_course_question" in available and "answer_course_question" not in skip_tools) or ("search_course_knowledge" in available and "search_course_knowledge" not in skip_tools)):
+        grounded_tool = "answer_course_question" if required_tools == ["answer_course_question"] and "answer_course_question" in available and "answer_course_question" not in skip_tools else "search_course_knowledge"
+        return host.force_tool(grounded_tool, goal, state, decision, reason="用户明确要求基于课程资料回答，必须使用可信问答内核" if grounded_tool == "answer_course_question" else "生成多模态产物前必须先检索课程依据")
+    if decision.status == "complete" and supervisor_intents.web_search_intent(goal) and "search_web" not in completed_tools and "search_web" in available and "search_web" not in skip_tools:
+        return host.force_tool("search_web", goal, state, decision, reason="用户要求联网搜索，必须先获取实时网页结果")
+    if decision.status == "complete" and pending:
+        tool_name = pending[0]
+        return host.force_tool(tool_name, goal, state, decision, reason=f"用户要求的{supervisor_intents.deliverable_label(tool_name)}尚未生成，禁止仅用文字/Markdown 代替")
+    if decision.status == "complete" and host.has_wrong_deliverable_only(state, goal):
+        wrong_pending = host.pending_deliverables(goal, available, completed_tools, skip_tools)
+        if wrong_pending:
+            tool_name = wrong_pending[0]
+            return host.force_tool(tool_name, goal, state, decision, reason=f"已调用错误工具，需补生成{supervisor_intents.deliverable_label(tool_name)}")
+    if decision.status == "complete":
+        decision.final_answer = normalize_completion_answer(state, goal, decision.final_answer)
+    if decision.status == "complete" and host.should_use_fallback_planner(goal, state, available, completed_tools, skip_tools, pending):
+        fallback = host.fallback_next_tool(goal, available, completed_tools, skip_tools)
+        if fallback:
+            return host.force_tool(fallback, goal, state, decision, reason=f"LLM 未调用工具，安全网补调 {fallback}")
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
diff --git a/backend/app/agent_runtime/tool_selector.py b/backend/app/agent_runtime/tool_selector.py
new file mode 100644
index 0000000..654dd28
--- /dev/null
+++ b/backend/app/agent_runtime/tool_selector.py
@@ -0,0 +1,66 @@
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
+    return [
+        item
+        for item in tool_schemas
+        if str(item.get("function", {}).get("name")) not in skipped
+    ]
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
diff --git a/backend/app/agent_runtime/tools.py b/backend/app/agent_runtime/tools.py
index abd8f83..d7edfdc 100644
--- a/backend/app/agent_runtime/tools.py
+++ b/backend/app/agent_runtime/tools.py
@@ -33,20 +33,21 @@ class ToolExecutionResult:
     artifact_refs: list[dict[str, Any]] = field(default_factory=list)
     citations: list[Any] = field(default_factory=list)
     error_message: str | None = None
     attempts: int = 1
     final_answer: str | None = None
 
 
 ToolHandler = Callable[[ToolContext, dict[str, Any]], Awaitable[ToolExecutionResult]]
 ResultLoader = Callable[[str], Awaitable[ToolExecutionResult | None]]
 ResultSaver = Callable[[str, ToolExecutionResult], Awaitable[None]]
+HandlerErrorRecovery = Callable[[Exception], Awaitable[None]]
 
 
 @dataclass
 class AgentTool:
     name: str
     description: str
     agent_name: str
     input_schema: dict[str, Any]
     handler: ToolHandler
     risk_level: Literal["low", "medium", "high"] = "low"
@@ -65,25 +66,27 @@ class AgentTool:
             },
         }
 
 
 class ToolRegistry:
     def __init__(
         self,
         *,
         result_loader: ResultLoader | None = None,
         result_saver: ResultSaver | None = None,
+        on_handler_error: HandlerErrorRecovery | None = None,
     ) -> None:
         self._tools: dict[str, AgentTool] = {}
         self._results: dict[str, ToolExecutionResult] = {}
         self._result_loader = result_loader
         self._result_saver = result_saver
+        self._on_handler_error = on_handler_error
 
     def register(self, tool: AgentTool) -> None:
         if tool.name in self._tools:
             raise ValueError(f"工具已注册: {tool.name}")
         self._tools[tool.name] = tool
 
     def get(self, name: str) -> AgentTool:
         tool = self._tools.get(name)
         if tool is None:
             raise ValueError(f"未知工具: {name}")
@@ -138,30 +141,40 @@ class ToolRegistry:
                 continue
             result.attempts = attempts
             self._results[context.idempotency_key] = result
             await self._save_result_safely(context.idempotency_key, result)
             return result
         result = ToolExecutionResult(
             success=False,
             error_message=str(last_error or "工具执行失败")[:2000],
             attempts=attempts,
         )
+        if last_error is not None:
+            await self._recover_from_handler_error(last_error)
         self._results[context.idempotency_key] = result
         await self._save_result_safely(context.idempotency_key, result)
         return result
 
     async def _save_result_safely(self, key: str, result: ToolExecutionResult) -> None:
         if self._result_saver is None:
             return
         try:
             await self._result_saver(key, result)
         except Exception:
             logger.exception("Agent tool result persistence failed for %s", key)
 
+    async def _recover_from_handler_error(self, error: Exception) -> None:
+        if self._on_handler_error is None:
+            return
+        try:
+            await self._on_handler_error(error)
+        except Exception:
+            logger.exception("Agent tool handler recovery failed")
+
     def _validate_arguments(self, tool: AgentTool, arguments: dict[str, Any]) -> None:
         schema = tool.input_schema or {"type": "object"}
         try:
             Draft202012Validator(schema).validate(arguments)
         except JsonSchemaValidationError as exc:
             path = ".".join(str(p) for p in exc.path)
             location = f" 参数 {path}" if path else ""
             raise ValueError(f"工具 {tool.name}{location} 校验失败: {exc.message}") from exc
diff --git a/backend/app/agent_runtime/toolsets/__init__.py b/backend/app/agent_runtime/toolsets/__init__.py
new file mode 100644
index 0000000..be76905
--- /dev/null
+++ b/backend/app/agent_runtime/toolsets/__init__.py
@@ -0,0 +1,13 @@
+from app.agent_runtime.toolsets.knowledge_tools import register_knowledge_tools
+from app.agent_runtime.toolsets.learning_tools import register_learning_tools
+from app.agent_runtime.toolsets.media_tools import register_media_tools
+from app.agent_runtime.toolsets.profile_tools import register_profile_tools
+from app.agent_runtime.toolsets.review_tools import register_review_tools
+
+__all__ = [
+    "register_knowledge_tools",
+    "register_learning_tools",
+    "register_media_tools",
+    "register_profile_tools",
+    "register_review_tools",
+]
diff --git a/backend/app/agent_runtime/toolsets/common.py b/backend/app/agent_runtime/toolsets/common.py
new file mode 100644
index 0000000..af0cd29
--- /dev/null
+++ b/backend/app/agent_runtime/toolsets/common.py
@@ -0,0 +1,39 @@
+from __future__ import annotations
+
+from typing import Any
+
+from app.agent_runtime.tools import AgentTool, ToolRegistry
+
+
+def register_tool(
+    registry: ToolRegistry,
+    name: str,
+    description: str,
+    agent_name: str,
+    properties: dict[str, Any],
+    required: list[str],
+    handler: Any,
+    *,
+    writes_db: bool = False,
+    risk_level: str = "low",
+    requires_confirmation: bool = False,
+    timeout_seconds: int = 120,
+) -> None:
+    registry.register(
+        AgentTool(
+            name=name,
+            description=description,
+            agent_name=agent_name,
+            input_schema={
+                "type": "object",
+                "properties": properties,
+                "required": required,
+                "additionalProperties": False,
+            },
+            handler=handler,
+            writes_db=writes_db,
+            risk_level=risk_level,  # type: ignore[arg-type]
+            requires_confirmation=requires_confirmation,
+            timeout_seconds=timeout_seconds,
+        )
+    )
diff --git a/backend/app/agent_runtime/toolsets/knowledge_tools.py b/backend/app/agent_runtime/toolsets/knowledge_tools.py
new file mode 100644
index 0000000..46a22c9
--- /dev/null
+++ b/backend/app/agent_runtime/toolsets/knowledge_tools.py
@@ -0,0 +1,139 @@
+from __future__ import annotations
+
+from collections.abc import Iterable
+from typing import Any
+from uuid import UUID
+
+from sqlalchemy.ext.asyncio import AsyncSession
+
+from app.agent_runtime.tools import ToolContext, ToolExecutionResult, ToolRegistry
+from app.agent_runtime.toolsets.common import register_tool
+from app.models.user import User
+
+
+def register_knowledge_tools(
+    registry: ToolRegistry,
+    db: AsyncSession,
+    current_user: User,
+    *,
+    tool_names: Iterable[str] | None = None,
+) -> None:
+    selected = set(tool_names or ())
+
+    def include(name: str) -> bool:
+        return not selected or name in selected
+
+    async def search_knowledge(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.services.knowledge_search_service import KnowledgeSearchService
+
+        payload = await KnowledgeSearchService(db).search(
+            current_user=current_user,
+            course_id=context.course_id,
+            query=str(arguments["query"]),
+            top_k=int(arguments.get("top_k") or 5),
+        )
+        items = payload.get("items") or []
+        graph_context = payload.get("graph_context") or {}
+        citations = [
+            {
+                "source_type": "document",
+                "title": item.get("source_title") or "课程资料",
+                "source_id": item.get("material_id"),
+                "chunk_id": item.get("chunk_id"),
+                "page_no": item.get("page_no"),
+                "score": item.get("score"),
+                "quote": str(item.get("content") or "")[:300],
+            }
+            for item in items
+        ]
+        return ToolExecutionResult(
+            output={"items": items, "graph_context": graph_context},
+            evidence=citations,
+            citations=citations,
+        )
+
+    async def search_web(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.services.web_search_service import WebSearchService
+
+        payload = await WebSearchService().search(
+            query=str(arguments["query"]),
+            max_results=int(arguments.get("max_results") or 5),
+            domain=str(arguments.get("domain") or "") or None,
+        )
+        citations = payload.get("citations") or []
+        return ToolExecutionResult(output=payload, evidence=citations, citations=citations)
+
+    async def parse_document(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.services.embedding_service import EmbeddingService
+        from app.services.material_service import MaterialService
+
+        material_id = UUID(str(arguments["material_id"]))
+        parse_result = await MaterialService(db).parse_material(
+            material_id=material_id,
+            current_user=current_user,
+        )
+        embedded_count = await EmbeddingService(db).generate_embeddings(material_id)
+        return ToolExecutionResult(
+            output={
+                "material_id": str(material_id),
+                "file_name": parse_result.file_name,
+                "text_length": parse_result.text_length,
+                "parse_status": parse_result.parse_status,
+                "embedded_count": embedded_count,
+            },
+            evidence=[
+                f"已解析 {parse_result.file_name}，提取 {parse_result.text_length} 字符",
+                f"已生成 {embedded_count} 个向量切片",
+            ],
+            artifact_refs=[{"type": "material", "id": str(material_id), "title": parse_result.file_name}],
+        )
+
+    async def generate_mindmap_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.services.mindmap_service import MindmapService
+
+        topic = str(arguments.get("topic") or "").strip() or "数据结构知识结构"
+        result = await MindmapService(db).generate(
+            current_user=current_user,
+            course_id=context.course_id,
+            topic=topic,
+            scope=str(arguments.get("scope") or "course"),
+            depth=int(arguments.get("depth") or 3),
+        )
+        return ToolExecutionResult(
+            output=result,
+            evidence=result.get("citations") or [],
+            citations=result.get("citations") or [],
+            artifact_refs=[
+                {"type": "resource", "subtype": "mindmap", "id": result["resource_id"], "title": result["title"]}
+            ],
+        )
+
+    async def generate_diagram_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.services.diagram_service import DiagramService
+
+        concept = str(arguments.get("concept") or "").strip() or "数据结构概念"
+        result = await DiagramService(db).generate(
+            current_user=current_user,
+            course_id=context.course_id,
+            concept=concept,
+            diagram_type=str(arguments.get("diagram_type") or "flowchart"),
+        )
+        return ToolExecutionResult(
+            output=result,
+            evidence=result.get("citations") or [],
+            citations=result.get("citations") or [],
+            artifact_refs=[
+                {"type": "resource", "subtype": "diagram", "id": result["resource_id"], "title": result["title"]}
+            ],
+        )
+
+    if include("search_course_knowledge"):
+        register_tool(registry, "search_course_knowledge", "使用向量、关键词、metadata 和 rerank 混合检索课程资料，返回可引用片段。", "KnowledgeAgent", {"query": {"type": "string"}, "top_k": {"type": "integer", "minimum": 1, "maximum": 20}}, ["query"], search_knowledge)
+    if include("search_web"):
+        register_tool(registry, "search_web", "通过 AnySearch 联网搜索互联网实时信息，返回可引用的网页标题、URL 与摘要。适用于最新资讯、公开资料、技术文档等课程库未覆盖的问题。", "KnowledgeAgent", {"query": {"type": "string", "description": "搜索关键词或完整问题"}, "max_results": {"type": "integer", "minimum": 1, "maximum": 10}, "domain": {"type": "string", "description": "可选垂直领域，如 general/academic/code/finance"}}, ["query"], search_web, timeout_seconds=45)
+    if include("parse_uploaded_document"):
+        register_tool(registry, "parse_uploaded_document", "解析已上传的课程资料（PDF/DOCX/TXT/MD），自动切片和向量化，供 RAG 检索使用。", "KnowledgeAgent", {"material_id": {"type": "string", "description": "课程资料 UUID"}}, ["material_id"], parse_document, writes_db=True)
+    if include("generate_mindmap"):
+        register_tool(registry, "generate_mindmap", "围绕课程知识点生成 Mermaid 思维导图，可视化知识结构关系。", "KnowledgeAgent", {"topic": {"type": "string", "description": "知识主题"}, "scope": {"type": "string", "enum": ["course", "chapter", "custom"]}, "depth": {"type": "integer", "minimum": 2, "maximum": 5}}, ["topic"], generate_mindmap_handler, writes_db=True)
+    if include("generate_diagram"):
+        register_tool(registry, "generate_diagram", "围绕知识概念生成流程图、架构图或示意图的 Mermaid 代码。", "KnowledgeAgent", {"concept": {"type": "string", "description": "需要图解的概念"}, "diagram_type": {"type": "string", "enum": ["flowchart", "sequence", "class", "er"]}}, ["concept"], generate_diagram_handler, writes_db=True)
diff --git a/backend/app/agent_runtime/toolsets/learning_tools.py b/backend/app/agent_runtime/toolsets/learning_tools.py
new file mode 100644
index 0000000..d6cb268
--- /dev/null
+++ b/backend/app/agent_runtime/toolsets/learning_tools.py
@@ -0,0 +1,154 @@
+from __future__ import annotations
+
+from collections.abc import Iterable
+from typing import Any
+
+from sqlalchemy.ext.asyncio import AsyncSession
+
+from app.agent_runtime.tools import ToolContext, ToolExecutionResult, ToolRegistry
+from app.agent_runtime.toolsets.common import register_tool
+from app.models.user import User
+
+
+def register_learning_tools(
+    registry: ToolRegistry,
+    db: AsyncSession,
+    current_user: User,
+    *,
+    tool_names: Iterable[str] | None = None,
+) -> None:
+    selected = set(tool_names or ())
+
+    def include(name: str) -> bool:
+        return not selected or name in selected
+
+    async def answer_question(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.schemas.tutor import TutorChatRequest
+        from app.services.grounded_qa_pipeline import GroundedQaPipeline
+
+        result = await GroundedQaPipeline(db).answer(
+            TutorChatRequest(
+                course_id=context.course_id,
+                conversation_id=context.conversation_id,
+                question=str(arguments["question"]),
+                top_k=int(arguments.get("top_k") or 5),
+            ),
+            current_user,
+            persist_conversation_messages=False,
+        )
+        data = result.model_dump(mode="json")
+        refs = [{"type": "tutor_answer", "id": str(result.message_id)}] if result.message_id else []
+        return ToolExecutionResult(
+            output=data,
+            evidence=data.get("citations") or [],
+            citations=data.get("citations") or [],
+            artifact_refs=refs,
+            final_answer=result.answer,
+        )
+
+    async def generate_path(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.schemas.learning_path import LearningPathGenerateRequest
+        from app.services.learning_path_service import LearningPathService
+
+        result = await LearningPathService(db).generate(
+            payload=LearningPathGenerateRequest(course_id=context.course_id, goal=str(arguments["goal"])),
+            current_user=current_user,
+        )
+        data = result.model_dump(mode="json")
+        return ToolExecutionResult(
+            output=data,
+            evidence=[result.reason or "基于课程知识点、画像和目标生成"],
+            artifact_refs=[{"type": "learning_path", "id": str(result.id), "title": result.title}],
+        )
+
+    async def generate_explanation(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.schemas.resource import ResourceGenerateRequest
+        from app.services.resource_service import ResourceService
+
+        topic = str(arguments["topic"])
+        result = await ResourceService(db).generate_resource(
+            payload=ResourceGenerateRequest(
+                course_id=context.course_id,
+                resource_type=str(arguments.get("resource_type") or "explanation"),
+                requirement=str(arguments.get("requirement") or f"围绕{topic}生成分步骤讲解并引用课程资料。"),
+                use_profile=True,
+            ),
+            current_user=current_user,
+        )
+        data = result.model_dump(mode="json")
+        return ToolExecutionResult(
+            output=data,
+            evidence=data.get("citations") or [],
+            citations=data.get("citations") or [],
+            artifact_refs=[
+                {
+                    "type": "resource",
+                    "subtype": data.get("resource_type"),
+                    "resource_type": data.get("resource_type"),
+                    "id": str(result.resource_id),
+                    "resource_id": str(result.resource_id),
+                    "title": result.title,
+                }
+            ],
+        )
+
+    async def generate_quiz(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.schemas.quiz import QuizGenerateRequest
+        from app.services.quiz_service import QuizService
+
+        result = await QuizService(db).generate_quiz(
+            payload=QuizGenerateRequest(
+                course_id=context.course_id,
+                topic=str(arguments["topic"]),
+                count=int(arguments.get("count") or 5),
+                difficulty=str(arguments.get("difficulty") or "medium"),
+                question_types=list(arguments.get("question_types") or ["single_choice"]),
+            ),
+            current_user=current_user,
+        )
+        data = result.model_dump(mode="json")
+        return ToolExecutionResult(
+            output=data,
+            evidence=[f"生成 {len(result.questions)} 道结构化练习"],
+            artifact_refs=[{"type": "quiz", "id": str(result.quiz_id), "title": result.title}],
+        )
+
+    async def analyze_diagnosis(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.services.diagnosis_service import DiagnosisService
+
+        result = await DiagnosisService(db).analyze(
+            current_user=current_user,
+            course_id=context.course_id,
+            trigger_evolution=False,
+        )
+        return ToolExecutionResult(
+            output=result,
+            evidence=result.get("weak_points") or [],
+            artifact_refs=[{"type": "diagnosis_report", "id": str(result.get("id") or "")}],
+        )
+
+    async def refresh_recommendations(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.services.recommendation_service import RecommendationService
+
+        result = await RecommendationService(db).refresh_recommendations(
+            current_user=current_user,
+            course_id=context.course_id,
+        )
+        return ToolExecutionResult(
+            output=result,
+            evidence=["基于画像、诊断与学习路径刷新"],
+            artifact_refs=[{"type": "recommendations", "count": result["refreshed_count"]}],
+        )
+
+    if include("answer_course_question"):
+        register_tool(registry, "answer_course_question", "基于课程知识库、Wiki 和学生画像回答学习问题。", "TutorAgent", {"question": {"type": "string"}, "top_k": {"type": "integer", "minimum": 1, "maximum": 20}}, ["question"], answer_question, writes_db=True)
+    if include("generate_learning_path"):
+        register_tool(registry, "generate_learning_path", "根据学习目标、薄弱点和课程知识点生成个性化学习路径。", "PlannerAgent", {"goal": {"type": "string"}}, ["goal"], generate_path, writes_db=True)
+    if include("generate_explanation"):
+        register_tool(registry, "generate_explanation", "围绕知识主题生成带来源和个性化理由的学习资源。", "ResourceAgent", {"topic": {"type": "string"}, "resource_type": {"type": "string", "enum": ["explanation", "summary", "example", "flashcard", "review"]}, "requirement": {"type": "string"}}, ["topic"], generate_explanation, writes_db=True)
+    if include("generate_quiz"):
+        register_tool(registry, "generate_quiz", "围绕主题生成结构化练习题。", "QuizAgent", {"topic": {"type": "string"}, "count": {"type": "integer", "minimum": 1, "maximum": 20}, "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]}, "question_types": {"type": "array", "items": {"type": "string"}}}, ["topic"], generate_quiz, writes_db=True)
+    if include("analyze_learning_diagnosis"):
+        register_tool(registry, "analyze_learning_diagnosis", "基于练习和错题生成学习诊断。", "DiagnosisAgent", {}, [], analyze_diagnosis, writes_db=True)
+    if include("refresh_recommendations"):
+        register_tool(registry, "refresh_recommendations", "根据画像、诊断和路径刷新推荐。", "RecommendAgent", {}, [], refresh_recommendations, writes_db=True)
diff --git a/backend/app/agent_runtime/toolsets/media_tools.py b/backend/app/agent_runtime/toolsets/media_tools.py
new file mode 100644
index 0000000..d056212
--- /dev/null
+++ b/backend/app/agent_runtime/toolsets/media_tools.py
@@ -0,0 +1,196 @@
+from __future__ import annotations
+
+from collections.abc import Iterable
+from typing import Any
+
+from sqlalchemy.ext.asyncio import AsyncSession
+
+from app.agent_runtime.tools import ToolContext, ToolExecutionResult, ToolRegistry
+from app.agent_runtime.toolsets.common import register_tool
+from app.models.user import User
+
+
+def register_media_tools(
+    registry: ToolRegistry,
+    db: AsyncSession,
+    current_user: User,
+    *,
+    tool_names: Iterable[str] | None = None,
+) -> None:
+    selected = set(tool_names or ())
+
+    def include(name: str) -> bool:
+        return not selected or name in selected
+
+    async def transcribe_audio_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.llm.audio_provider import _safe_audio_byte_count, build_audio_provider
+
+        audio_base64 = str(arguments["audio_base64"])
+        byte_count = _safe_audio_byte_count(audio_base64)
+        result = await build_audio_provider().transcribe(
+            audio_base64,
+            filename=str(arguments.get("filename") or "audio.wav"),
+            language=str(arguments.get("language") or "zh"),
+        )
+        raw = result.raw or {}
+        return ToolExecutionResult(
+            output={
+                "text": result.text,
+                "duration_ms": result.duration_ms,
+                "language": result.language,
+                "provider": result.provider,
+                "model": result.model,
+                "audio_bytes": byte_count,
+                "fallback_used": bool(raw.get("fallback_used")),
+                "failed_provider": raw.get("failed_provider"),
+                "fallback_reason": raw.get("fallback_reason"),
+            },
+            evidence=[f"语音识别完成，provider={result.provider}，模型={result.model}", f"输入音频 {byte_count} bytes，识别文本 {len(result.text)} 字"],
+        )
+
+    async def synthesize_speech_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        import base64
+
+        from app.llm.audio_provider import MIMO_TTS_MODEL, MIMO_TTS_VOICECLONE_MODEL, MIMO_TTS_VOICEDESIGN_MODEL, build_audio_provider
+        from app.repositories.media_repository import MediaRepository
+        from app.services.media_storage_service import MediaStorageService
+
+        text = str(arguments["text"]).strip()
+        model_type = str(arguments.get("model_type") or "tts")
+        model_map = {"tts": MIMO_TTS_MODEL, "voiceclone": MIMO_TTS_VOICECLONE_MODEL, "voicedesign": MIMO_TTS_VOICEDESIGN_MODEL}
+        result = await build_audio_provider().synthesize(
+            text,
+            voice=str(arguments.get("voice") or "") or None,
+            speed=float(arguments.get("speed") or 1.0),
+            response_format=str(arguments.get("response_format") or "wav"),
+            model=model_map.get(model_type, MIMO_TTS_MODEL),
+        )
+        raw = result.raw or {}
+        audio_format = result.format or "wav"
+        padding = "=" * (-len(result.audio_base64) % 4)
+        audio_bytes = base64.b64decode(result.audio_base64 + padding)
+        storage_path, file_size, mime_type = MediaStorageService().save_bytes(data=audio_bytes, asset_type="audio", suffix=f".{audio_format}")
+        topic = text[:30].replace("\n", " ")
+        asset = await MediaRepository(db).create_asset(
+            user_id=current_user.id,
+            course_id=context.course_id,
+            asset_type="audio",
+            title=f"语音讲解 · {topic}",
+            storage_path=storage_path,
+            mime_type=mime_type,
+            file_size=file_size,
+            duration_ms=result.duration_ms,
+            agent_task_id=context.task_id,
+            tool_call_id=context.tool_call_id,
+            provider=result.provider,
+            model_name=result.model,
+            prompt=text[:2000],
+        )
+        return ToolExecutionResult(
+            output={
+                "asset_id": str(asset.id),
+                "audio_base64": result.audio_base64,
+                "format": audio_format,
+                "model": result.model,
+                "provider": result.provider,
+                "duration_ms": result.duration_ms,
+                "text_length": len(text),
+                "fallback_used": bool(raw.get("fallback_used")),
+                "failed_provider": raw.get("failed_provider"),
+                "fallback_reason": raw.get("fallback_reason"),
+            },
+            evidence=[f"语音合成完成，provider={result.provider}，模型={result.model}", f"输出格式 {audio_format}，文本 {len(text)} 字"],
+            artifact_refs=[{"type": "audio", "asset_id": str(asset.id), "title": asset.title, "mime_type": mime_type}],
+        )
+
+    async def generate_educational_image_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.services.multimodal_resource_service import MultimodalResourceService
+
+        result = await MultimodalResourceService(db).generate_image(
+            current_user=current_user,
+            course_id=context.course_id,
+            topic=str(arguments["topic"]),
+            image_type=str(arguments.get("image_type") or "concept_illustration"),
+            style=str(arguments.get("style") or "clean educational illustration"),
+            size=str(arguments.get("size") or "1280x720"),
+            requirement=str(arguments.get("requirement") or "") or None,
+            tool_context=context,
+        )
+        mode = str(result.get("generation_mode") or "image")
+        if mode.startswith("mermaid"):
+            subtype = str(result.get("subtype") or "mindmap")
+            return ToolExecutionResult(output=result, evidence=result.get("citations") or [], citations=result.get("citations") or [], artifact_refs=[{"type": "resource", "subtype": subtype, "id": result["resource_id"], "title": result.get("title")}])
+        return ToolExecutionResult(output=result, evidence=result.get("citations") or [], citations=result.get("citations") or [], artifact_refs=[{"type": "media_asset", "subtype": "image", **result}])
+
+    async def generate_lesson_video_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.services.multimodal_resource_service import MultimodalResourceService
+
+        result = await MultimodalResourceService(db).create_video_job(
+            current_user=current_user,
+            course_id=context.course_id,
+            topic=str(arguments["topic"]),
+            duration_seconds=int(arguments.get("duration_seconds") or 90),
+            visual_mode=str(arguments.get("visual_mode") or "storyboard"),
+            voice=str(arguments.get("voice") or "") or None,
+            target_level=str(arguments.get("target_level") or "") or None,
+            tool_context=context,
+        )
+        return ToolExecutionResult(output=result, evidence=["视频生成任务已创建，后台会持续写入进度事件。"], artifact_refs=[{"type": "media_job", "subtype": "video", **result}])
+
+    async def generate_immersive_classroom_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.services.immersive_classroom_service import ImmersiveClassroomService
+
+        result = await ImmersiveClassroomService(db).create_job(
+            current_user=current_user,
+            course_id=context.course_id,
+            topic=str(arguments["topic"]),
+            learning_goal=str(arguments.get("learning_goal") or "") or None,
+            generate_video_export=bool(arguments.get("generate_video_export", True)),
+            enable_images=bool(arguments.get("enable_images", True)),
+            enable_video_clips=bool(arguments.get("enable_video_clips", False)),
+            enable_tts=bool(arguments.get("enable_tts", True)),
+            tool_context=context,
+        )
+        return ToolExecutionResult(output=result, evidence=["已创建基于课程 RAG 与学生画像的沉浸课堂任务，后台将继续生成课堂和配音字幕 MP4。"], artifact_refs=[{"type": "media_job", "subtype": "immersive_classroom", **result}])
+
+    async def generate_storyboard_html_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.services.multimodal_resource_service import MultimodalResourceService
+
+        result = await MultimodalResourceService(db).generate_storyboard_html(
+            current_user=current_user,
+            course_id=context.course_id,
+            topic=str(arguments["topic"]),
+            duration_seconds=int(arguments.get("duration_seconds") or 90),
+            requirement=str(arguments.get("requirement") or "") or None,
+            tool_context=context,
+        )
+        return ToolExecutionResult(output=result, evidence=result.get("citations") or [], citations=result.get("citations") or [], artifact_refs=[{"type": "media_asset", "subtype": "storyboard", **result}])
+
+    async def generate_interactive_courseware_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.services.multimodal_resource_service import MultimodalResourceService
+
+        result = await MultimodalResourceService(db).generate_courseware(
+            current_user=current_user,
+            course_id=context.course_id,
+            topic=str(arguments["topic"]),
+            interaction_type=str(arguments.get("interaction_type") or "stepper"),
+            target_level=str(arguments.get("target_level") or "") or None,
+            requirement=str(arguments.get("requirement") or "") or None,
+            tool_context=context,
+        )
+        return ToolExecutionResult(output=result, evidence=result.get("citations") or [], citations=result.get("citations") or [], artifact_refs=[{"type": "media_asset", "subtype": "courseware", **result}])
+
+    if include("transcribe_audio"):
+        register_tool(registry, "transcribe_audio", "将音频文件转换为文字，支持语音提问、语音笔记等场景。", "TutorAgent", {"audio_base64": {"type": "string", "description": "Base64 编码的音频数据"}, "filename": {"type": "string", "description": "文件名（用于推断格式）"}, "language": {"type": "string", "description": "语言代码，默认 zh"}}, ["audio_base64"], transcribe_audio_handler, timeout_seconds=60)
+    if include("synthesize_speech"):
+        register_tool(registry, "synthesize_speech", "将文字转换为语音，用于讲解朗读、错题语音反馈等场景。", "TutorAgent", {"text": {"type": "string", "description": "要转换的文字"}, "model_type": {"type": "string", "enum": ["tts", "voiceclone", "voicedesign"]}, "voice": {"type": "string", "description": "音色，可由具体 Provider 解释"}, "speed": {"type": "number", "minimum": 0.5, "maximum": 2.0}, "response_format": {"type": "string", "enum": ["wav", "mp3"]}}, ["text"], synthesize_speech_handler, timeout_seconds=120)
+    if include("generate_educational_image"):
+        register_tool(registry, "generate_educational_image", "基于课程资料、学生画像和知识主题生成教学插图、概念图、类比图或封面图。", "VisualResourceAgent", {"topic": {"type": "string", "minLength": 1}, "image_type": {"type": "string", "enum": ["concept_illustration", "process_visual", "analogy", "cover", "summary_card"]}, "style": {"type": "string"}, "size": {"type": "string", "enum": ["1024x1024", "1280x720", "720x1280", "1024x768"]}, "requirement": {"type": "string"}}, ["topic"], generate_educational_image_handler, writes_db=True, timeout_seconds=180)
+    if include("generate_immersive_classroom"):
+        register_tool(registry, "generate_immersive_classroom", "基于课程资料、学生画像与薄弱点，一键生成 OpenMAIC 沉浸课堂，并可导出配音字幕知识点讲解 MP4。", "ImmersiveClassroomAgent", {"topic": {"type": "string", "minLength": 1}, "learning_goal": {"type": "string"}, "generate_video_export": {"type": "boolean"}, "enable_images": {"type": "boolean"}, "enable_video_clips": {"type": "boolean"}, "enable_tts": {"type": "boolean"}}, ["topic"], generate_immersive_classroom_handler, writes_db=True, timeout_seconds=30)
+    if include("generate_lesson_video"):
+        register_tool(registry, "generate_lesson_video", "创建短讲解视频（MP4）生成任务。仅当用户明确要「视频/短视频/动画讲解」时使用；PPT/幻灯片/课件应使用 generate_interactive_courseware。", "VideoResourceAgent", {"topic": {"type": "string", "minLength": 1}, "duration_seconds": {"type": "integer", "minimum": 30, "maximum": 240}, "visual_mode": {"type": "string", "enum": ["storyboard", "animated_diagram", "t2v_broll", "mixed"]}, "voice": {"type": "string"}, "target_level": {"type": "string"}}, ["topic"], generate_lesson_video_handler, writes_db=True, timeout_seconds=30)
+    if include("generate_storyboard_html"):
+        register_tool(registry, "generate_storyboard_html", "基于课程资料生成分镜 HTML 讲解页，可在 sandbox iframe 中预览（文生视频演示替代）。", "VideoResourceAgent", {"topic": {"type": "string", "minLength": 1}, "duration_seconds": {"type": "integer", "minimum": 30, "maximum": 240}, "requirement": {"type": "string"}}, ["topic"], generate_storyboard_html_handler, writes_db=True, timeout_seconds=120)
+    if include("generate_interactive_courseware"):
+        register_tool(registry, "generate_interactive_courseware", "基于 html-ppt-skill 生成多页 HTML 互动课件（PPT/幻灯片/slides/deck）。用户要 ppt、课件、幻灯片、翻页演示时用此工具，不是讲解视频。", "CoursewareAgent", {"topic": {"type": "string", "minLength": 1}, "interaction_type": {"type": "string", "enum": ["stepper", "drag_sort", "quiz_simulation", "graph_traversal", "timeline"]}, "target_level": {"type": "string"}, "requirement": {"type": "string"}}, ["topic"], generate_interactive_courseware_handler, writes_db=True, timeout_seconds=180)
diff --git a/backend/app/agent_runtime/toolsets/profile_tools.py b/backend/app/agent_runtime/toolsets/profile_tools.py
new file mode 100644
index 0000000..544e03e
--- /dev/null
+++ b/backend/app/agent_runtime/toolsets/profile_tools.py
@@ -0,0 +1,91 @@
+from __future__ import annotations
+
+from collections.abc import Iterable
+from typing import Any
+from uuid import UUID
+
+from sqlalchemy.ext.asyncio import AsyncSession
+
+from app.agent_runtime.tools import ToolContext, ToolExecutionResult, ToolRegistry
+from app.agent_runtime.toolsets.common import register_tool
+from app.models.user import User
+
+
+def register_profile_tools(
+    registry: ToolRegistry,
+    db: AsyncSession,
+    current_user: User,
+    *,
+    tool_names: Iterable[str] | None = None,
+) -> None:
+    selected = set(tool_names or ())
+
+    def include(name: str) -> bool:
+        return not selected or name in selected
+
+    async def rebuild_profile(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.services.profile_service import ProfileService
+
+        result = await ProfileService(db).rebuild(current_user.id)
+        data = result.model_dump(mode="json")
+        return ToolExecutionResult(
+            output=data,
+            evidence=["基于当前用户学习记录重建"],
+            artifact_refs=[{"type": "profile_update", "id": str(result.id)}],
+        )
+
+    async def update_profile_from_dialogue(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.services.profile_service import ProfileService
+
+        result = await ProfileService(db).ingest_dialogue_profile(
+            user_id=current_user.id,
+            course_id=context.course_id,
+            dialogue_text=str(arguments["dialogue_text"]),
+            source_message_id=str(arguments.get("source_message_id") or context.tool_call_id),
+        )
+        data = result.model_dump(mode="json")
+        artifact_refs = [{"type": "profile_update", "id": str(result.profile.id)}]
+        if result.preferences is not None:
+            artifact_refs.append({"type": "learning_preference", "id": str(result.preferences.id)})
+        return ToolExecutionResult(output=data, evidence=[data.get("evidence") or {}], artifact_refs=artifact_refs)
+
+    async def reflect_memory(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.services.memory_service import MemoryService
+
+        results = await MemoryService(db).reflect(current_user.id, context.course_id)
+        data = [item.model_dump(mode="json") for item in results]
+        return ToolExecutionResult(
+            output={"items": data},
+            evidence=[{"memory_id": str(item.id), "evidence": item.evidence} for item in results],
+            artifact_refs=[{"type": "memory_reflection", "count": len(results)}],
+        )
+
+    async def apply_evolution(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.services.evolution_service import EvolutionService
+
+        service = EvolutionService(db)
+        strategy_id = arguments.get("strategy_id")
+        if not strategy_id:
+            items, _ = await service.list_strategies(
+                user_id=current_user.id,
+                course_id=context.course_id,
+                status="draft",
+                page_size=1,
+            )
+            if not items:
+                raise RuntimeError("当前没有可应用的草稿自进化策略")
+            strategy_id = items[0].id
+        result = await service.apply_strategy(UUID(str(strategy_id)), current_user.id)
+        return ToolExecutionResult(
+            output=result.model_dump(mode="json"),
+            artifact_refs=[{"type": "evolution_strategy", "id": str(result.id), "status": result.status}],
+        )
+
+    if include("update_profile_from_dialogue"):
+        register_tool(registry, "update_profile_from_dialogue", "从学生自然语言对话中提取学习目标、专业年级、偏好、薄弱点和错误模式，并带证据更新画像。", "ProfileAgent", {"dialogue_text": {"type": "string"}, "source_message_id": {"type": "string"}}, ["dialogue_text"], update_profile_from_dialogue, writes_db=True)
+    if include("rebuild_profile"):
+        register_tool(registry, "rebuild_profile", "基于学习证据重建学生画像。", "ProfileAgent", {}, [], rebuild_profile, writes_db=True)
+    if include("reflect_learning_memory"):
+        register_tool(registry, "reflect_learning_memory", "提炼带证据的长期学习记忆。", "MemoryAgent", {}, [], reflect_memory, writes_db=True)
+    if include("apply_evolution_strategy"):
+        register_tool(registry, "apply_evolution_strategy", "应用已生成的自进化策略。该操作必须获得用户确认。", "EvolutionAgent", {"strategy_id": {"type": "string"}}, [], apply_evolution, writes_db=True, risk_level="high", requires_confirmation=True)
diff --git a/backend/app/agent_runtime/toolsets/review_tools.py b/backend/app/agent_runtime/toolsets/review_tools.py
new file mode 100644
index 0000000..3795096
--- /dev/null
+++ b/backend/app/agent_runtime/toolsets/review_tools.py
@@ -0,0 +1,53 @@
+from __future__ import annotations
+
+from collections.abc import Iterable
+from typing import Any
+from uuid import UUID
+
+from sqlalchemy.ext.asyncio import AsyncSession
+
+from app.agent_runtime.tools import ToolContext, ToolExecutionResult, ToolRegistry
+from app.agent_runtime.toolsets.common import register_tool
+from app.models.user import User
+
+
+def register_review_tools(
+    registry: ToolRegistry,
+    db: AsyncSession,
+    current_user: User,
+    *,
+    tool_names: Iterable[str] | None = None,
+) -> None:
+    selected = set(tool_names or ())
+
+    def include(name: str) -> bool:
+        return not selected or name in selected
+
+    async def review_artifacts(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.services.agent_service import AgentService
+
+        result = await AgentService(db).run_task(
+            task_type="review_content",
+            user_id=current_user.id,
+            course_id=context.course_id,
+            params={"content": str(arguments.get("content") or "")[:4000]},
+        )
+        if not result.success:
+            raise RuntimeError(result.message)
+        return ToolExecutionResult(output=result.data, evidence=result.evidence)
+
+    async def review_multimodal_asset_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
+        from app.services.multimodal_review_service import MultimodalReviewService
+
+        asset_id = UUID(str(arguments["asset_id"]))
+        result = await MultimodalReviewService(db).review_asset(asset_id, current_user.id)
+        return ToolExecutionResult(
+            output=result,
+            evidence=[f"多模态审核完成，risk={result['risk_level']}，引用 {result['citation_count']} 条", *(result.get("issues") or [])],
+            artifact_refs=[{"type": "media_review", "asset_id": result["asset_id"], "risk_level": result["risk_level"], "passed": result["passed"]}],
+        )
+
+    if include("review_artifacts"):
+        register_tool(registry, "review_artifacts", "审查生成内容的来源、幻觉和风险。", "ReviewAgent", {"content": {"type": "string"}}, ["content"], review_artifacts)
+    if include("review_multimodal_asset"):
+        register_tool(registry, "review_multimodal_asset", "审核图片、视频、互动课件等多模态产物的事实依据、安全风险、版权风险与可访问性。", "ReviewAgent", {"asset_id": {"type": "string", "minLength": 1}}, ["asset_id"], review_multimodal_asset_handler)
diff --git a/backend/app/agents/structured_outputs.py b/backend/app/agents/structured_outputs.py
index efdfcb0..b8e2f14 100644
--- a/backend/app/agents/structured_outputs.py
+++ b/backend/app/agents/structured_outputs.py
@@ -1,17 +1,17 @@
 """Pydantic schemas for Agent structured_chat() outputs."""
 
 from __future__ import annotations
 
 from typing import Any, Literal
 
-from pydantic import BaseModel, ConfigDict, Field, field_validator
+from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
 
 
 class QuizQuestionLLM(BaseModel):
     model_config = ConfigDict(extra="ignore")
 
     question_type: str | None = None
     difficulty: str | None = None
     question_text: str | None = None
     stem: str | None = None
     options: list[Any] | dict[str, Any] | None = None
@@ -29,20 +29,35 @@ class QuizGenerationOutput(BaseModel):
 
 
 class ReviewOutput(BaseModel):
     model_config = ConfigDict(extra="ignore", populate_by_name=True)
 
     passed: bool = Field(default=True, alias="pass")
     risk_level: Literal["low", "medium", "high"] = "medium"
     issues: list[str] = Field(default_factory=list)
     revision_suggestions: str | list[str] = ""
 
+    @field_validator("issues", mode="before")
+    @classmethod
+    def normalize_issues(cls, value: object) -> list[str]:
+        if not isinstance(value, list):
+            return [str(value)] if value else []
+        normalized: list[str] = []
+        for item in value:
+            if isinstance(item, dict):
+                category = str(item.get("type") or "问题").strip()
+                description = str(item.get("description") or item.get("message") or "").strip()
+                normalized.append(f"{category}：{description}" if description else category)
+            elif str(item).strip():
+                normalized.append(str(item))
+        return normalized
+
     @field_validator("risk_level", mode="before")
     @classmethod
     def normalize_risk(cls, value: object) -> str:
         text = str(value or "medium").lower()
         if text in {"low", "medium", "high"}:
             return text
         return "medium"
 
     def to_dict(self) -> dict[str, Any]:
         suggestions = self.revision_suggestions
@@ -66,29 +81,45 @@ class EvolutionStrategyItem(BaseModel):
     change_summary: str = ""
     risk_level: str = "medium"
     evidence: list[Any] | dict[str, Any] | str | None = None
 
 
 class EvolutionAnalysisOutput(BaseModel):
     model_config = ConfigDict(extra="ignore")
 
     strategies: list[EvolutionStrategyItem] = Field(min_length=1)
 
+    @model_validator(mode="before")
+    @classmethod
+    def wrap_flat_strategy(cls, value: object) -> object:
+        if not isinstance(value, dict) or "strategies" in value:
+            return value
+        return {"strategies": [value]}
+
 
 class MemoryItemOutput(BaseModel):
     model_config = ConfigDict(extra="ignore")
 
     memory_type: str = "insight"
     content: str = ""
     evidence: list[str] = Field(default_factory=list)
     confidence: float = 0.8
 
+    @field_validator("evidence", mode="before")
+    @classmethod
+    def normalize_evidence(cls, value: object) -> list[str]:
+        if value is None:
+            return []
+        if isinstance(value, list):
+            return [str(item) for item in value if str(item).strip()]
+        return [str(value)] if str(value).strip() else []
+
 
 class MemoryReflectOutput(BaseModel):
     model_config = ConfigDict(extra="ignore")
 
     memories: list[MemoryItemOutput] = Field(default_factory=list)
 
 
 class ProfileRebuildOutput(BaseModel):
     model_config = ConfigDict(extra="ignore")
 
diff --git a/backend/app/repositories/agent_task_repository.py b/backend/app/repositories/agent_task_repository.py
index 2848f86..c59f57b 100644
--- a/backend/app/repositories/agent_task_repository.py
+++ b/backend/app/repositories/agent_task_repository.py
@@ -1,18 +1,18 @@
 from __future__ import annotations
 
 from typing import Any
 from uuid import UUID
 
 from datetime import datetime
 
-from sqlalchemy import or_, select
+from sqlalchemy import or_, select, update
 from sqlalchemy.ext.asyncio import AsyncSession
 
 from app.models.agent_task import AgentTask, AgentTaskStep
 from app.schemas.agent_task import AgentTaskPlan
 
 
 class AgentTaskRepository:
     def __init__(self, db: AsyncSession) -> None:
         self.db = db
 
@@ -22,20 +22,32 @@ class AgentTaskRepository:
             .where(
                 AgentTask.status == "queued",
                 AgentTask.started_at.is_(None),
                 AgentTask.runtime_mode == "langgraph",
             )
             .order_by(AgentTask.created_at.asc())
             .limit(limit)
         )
         return list(result.scalars().all())
 
+    async def claim_queued_task(self, task_id: UUID, started_at: datetime) -> bool:
+        result = await self.db.execute(
+            update(AgentTask)
+            .where(
+                AgentTask.id == task_id,
+                AgentTask.status == "queued",
+                AgentTask.runtime_mode == "langgraph",
+            )
+            .values(status="running", started_at=started_at, error_message=None)
+        )
+        return result.rowcount == 1
+
     async def list_stale_running_tasks(self, *, older_than: datetime, limit: int = 20) -> list[AgentTask]:
         result = await self.db.execute(
             select(AgentTask)
             .where(
                 AgentTask.status == "running",
                 AgentTask.runtime_mode == "langgraph",
                 or_(
                     AgentTask.last_event_at.is_(None),
                     AgentTask.last_event_at < older_than,
                 ),
diff --git a/backend/app/services/agent_runtime_service.py b/backend/app/services/agent_runtime_service.py
index 7df0309..d632a42 100644
--- a/backend/app/services/agent_runtime_service.py
+++ b/backend/app/services/agent_runtime_service.py
@@ -26,77 +26,78 @@ class AgentTaskCancelled(RuntimeError):
 
 
 class AgentRuntimeService:
     def __init__(self, db: AsyncSession, *, broker: AgentEventBroker | None = None) -> None:
         self.db = db
         self.tasks = AgentTaskRepository(db)
         self.conversations = AgentConversationRepository(db)
         self.broker = broker or AgentEventBroker()
 
     async def execute(self, task_id: UUID, *, approved: bool | None = None) -> dict[str, Any]:
-        task = await self._get_task(task_id)
-        if task.status == "cancelled":
-            return {"status": "cancelled", "final_answer": "任务已由用户取消。"}
-        user = await self._get_user(task.user_id)
-        messages = await self.conversations.list_messages(task.conversation_id, limit=80)
-        provider = get_llm_provider(
-            db=self.db,
-            user_id=task.user_id,
-            course_id=task.course_id,
-            allow_mock_fallback=False,
-        )
-        registry = build_learning_tool_registry(
-            self.db,
-            user,
-            result_loader=self._load_tool_result,
-            result_saver=self._save_tool_result,
-        )
-        supervisor = MiMoSupervisor(provider=provider)
-
-        async def context_loader(state) -> dict[str, Any]:
-            return await self._load_context(task, user)
-
-        async def reviewer(state) -> dict[str, Any]:
-            from app.services.agent_service import AgentService
+        if not await self.tasks.claim_queued_task(task_id, datetime.now(UTC)):
+            return {"status": "already_claimed"}
+        await self.db.commit()
 
-            content = {
-                "goal": state.get("goal"),
-                "final_answer": state.get("final_answer"),
-                "artifacts": state.get("artifacts") or [],
-                "citations": state.get("citations") or [],
-            }
-            result = await AgentService(self.db).run_task(
-                task_type="review_content",
-                user_id=user.id,
+        task: AgentTask | None = None
+        try:
+            task = await self._get_task(task_id)
+            if task.status == "cancelled":
+                await self.db.rollback()
+                return {"status": "cancelled", "final_answer": "任务已由用户取消。"}
+            user = await self._get_user(task.user_id)
+            messages = await self.conversations.list_messages(task.conversation_id, limit=80)
+            provider = get_llm_provider(
+                db=self.db,
+                user_id=task.user_id,
                 course_id=task.course_id,
-                params={"content": str(content)[:4000]},
+                allow_mock_fallback=False,
+            )
+            registry = build_learning_tool_registry(
+                self.db,
+                user,
+                result_loader=self._load_tool_result,
+                result_saver=self._save_tool_result,
             )
-            return result.data if result.success else {"pass": False, "issues": [result.message]}
+            supervisor = MiMoSupervisor(provider=provider)
+
+            async def context_loader(state) -> dict[str, Any]:
+                context = await self._load_context(task, user)
+                await self.db.commit()
+                return context
+
+            async def reviewer(state) -> dict[str, Any]:
+                from app.services.agent_service import AgentService
+
+                content = {
+                    "goal": state.get("goal"),
+                    "final_answer": state.get("final_answer"),
+                    "artifacts": state.get("artifacts") or [],
+                    "citations": state.get("citations") or [],
+                }
+                result = await AgentService(self.db).run_task(
+                    task_type="review_content",
+                    user_id=user.id,
+                    course_id=task.course_id,
+                    params={"content": str(content)[:4000]},
+                )
+                return result.data if result.success else {"pass": False, "issues": [result.message]}
 
-        async def memory_reflector(state) -> dict[str, Any]:
-            from app.services.memory_service import MemoryService
+            async def memory_reflector(state) -> dict[str, Any]:
+                from app.services.memory_service import MemoryService
 
-            await MemoryService(self.db).reflect(user.id, task.course_id)
-            return {}
+                await MemoryService(self.db).reflect(user.id, task.course_id)
+                return {}
 
-        async def event_sink(event_type: str, state, payload: dict[str, Any]) -> None:
-            await self._record_event(task, registry, event_type, state, payload)
+            async def event_sink(event_type: str, state, payload: dict[str, Any]) -> None:
+                await self._record_event(task, registry, event_type, state, payload)
 
-        await self.tasks.update_task(
-            task,
-            status="running",
-            started_at=task.started_at or datetime.now(UTC),
-            error_message=None,
-        )
-        await self.db.commit()
-
-        try:
+            await self.db.commit()
             async with AsyncPostgresSaver.from_conn_string(_psycopg_url(settings.database_url)) as checkpointer:
                 graph = LearningAgentGraph(
                     registry=registry,
                     supervisor=supervisor,
                     checkpointer=checkpointer,
                     context_loader=context_loader,
                     reviewer=reviewer,
                     memory_reflector=memory_reflector,
                     event_sink=event_sink,
                 )
@@ -114,25 +115,31 @@ class AgentRuntimeService:
                         max_tool_calls=settings.agent_max_tool_calls,
                         max_replans=settings.agent_max_replans,
                         tool_hints=list(input_payload.get("tool_hints") or []),
                         skip_tools=list(input_payload.get("skip_tools") or []),
                         tool_topics=dict(input_payload.get("tool_topics") or {}),
                         parsed_intents=list(input_payload.get("parsed_intents") or []),
                     )
                 else:
                     result = await graph.resume(thread_id=task.thread_id or str(task.id), approved=approved)
         except AgentTaskCancelled:
+            await self.db.rollback()
             return {"status": "cancelled", "final_answer": "任务已由用户取消。"}
         except Exception as exc:
-            await self._mark_failed(task, exc)
+            await self.db.rollback()
+            if task is None:
+                task = await self._get_task_optional(task_id)
+            if task is not None:
+                await self._mark_failed(task, exc)
             raise
 
+        assert task is not None
         await self._finish_task(task, result)
         return result
 
     async def _load_context(self, task: AgentTask, user: User) -> dict[str, Any]:
         from app.services.memory_service import MemoryService
         from app.services.profile_context_cache import ProfileContextCache
         from app.services.profile_service import ProfileService
 
         profile = await ProfileContextCache().get_or_load(
             user.id,
@@ -198,20 +205,27 @@ class AgentRuntimeService:
                     iteration_no=int(state.get("iteration_count") or 0),
                     status="running",
                     input_payload=dict(payload.get("arguments") or {}),
                     output_payload={},
                     evidence=[],
                     artifact_refs=[],
                     error_message=None,
                     retry_count=0,
                     decision_summary=state.get("decision_summary"),
                 )
+        elif event_type == "tool_completed":
+            tool_call_id = str(payload.get("tool_call_id") or "")
+            duration_ms = payload.get("duration_ms")
+            if tool_call_id and isinstance(duration_ms, int):
+                step = await self.tasks.get_step_by_tool_call(task.id, tool_call_id)
+                if step is not None:
+                    await self.tasks.update_step(step, duration_ms=duration_ms)
         await self.db.commit()
         await self.broker.publish(task.id, event_type, {**payload, "sequence_no": event.sequence_no})
 
     async def _mark_failed(self, task: AgentTask, exc: Exception) -> None:
         current = await self._get_task_optional(task.id)
         if current is None or current.status == "cancelled":
             return
         message = str(exc)[:2000] or exc.__class__.__name__
         await self.tasks.update_task(
             current,
@@ -258,20 +272,21 @@ class AgentRuntimeService:
         if result.final_answer:
             output_payload["_final_answer"] = result.final_answer
         await self.tasks.update_step(
             step,
             status="succeeded" if result.success else "failed",
             output_payload=output_payload,
             evidence=result.evidence,
             artifact_refs=result.artifact_refs,
             error_message=result.error_message,
             retry_count=max(0, result.attempts - 1),
+            duration_ms=getattr(result, "duration_ms", None),
             finished_at=datetime.now(UTC),
         )
         await self.db.commit()
 
     async def _finish_task(self, task: AgentTask, result: dict[str, Any]) -> None:
         current = await self._get_task(task.id)
         if current.status == "cancelled":
             return
         status = result.get("status")
         values: dict[str, Any] = {
diff --git a/backend/app/services/prompt_service.py b/backend/app/services/prompt_service.py
index 756afd9..71a1b28 100644
--- a/backend/app/services/prompt_service.py
+++ b/backend/app/services/prompt_service.py
@@ -128,21 +128,21 @@ DEFAULT_PROMPTS: dict[tuple[str, str], str] = {
         "请根据答题记录、错题模式和学习行为生成学习诊断。\n\n"
         "输入数据：{diagnosis_context}\n\n"
         "输出薄弱点、错因模式、证据和下一步建议。"
     ),
     (
         "EvolutionAgent",
         "evolution.analyze",
     ): (
         "请分析是否需要更新学习策略。自进化只能更新画像、偏好、Prompt 参数和推荐策略，不能修改代码、数据库结构或权限。\n\n"
         "证据：{evidence}\n\n"
-        "输出 change_summary、before_snapshot、after_snapshot、risk_level 和 rollback 说明。"
+        "只输出 JSON 对象：{{\"strategies\":[{{\"strategy_type\":\"recommendation\",\"change_summary\":\"说明\",\"before_value\":{{}},\"after_value\":{{}},\"risk_level\":\"low|medium|high\",\"evidence\":[\"证据\"]}}]}}。"
     ),
     (
         "ReviewAgent",
         "review.check",
     ): (
         "请审查 AI 生成内容是否有来源、是否偏离知识点、是否存在明显幻觉以及风险等级是否合理。\n\n"
         "待审查内容：{content}\n\n"
         "输出 pass、issues、risk_level 和 revision_suggestions。"
     ),
 }
diff --git a/backend/tests/test_agent_cancellation.py b/backend/tests/test_agent_cancellation.py
index 9d0e358..da39b00 100644
--- a/backend/tests/test_agent_cancellation.py
+++ b/backend/tests/test_agent_cancellation.py
@@ -1,34 +1,40 @@
 from __future__ import annotations
 
+from datetime import UTC, datetime
 from types import SimpleNamespace
 from unittest.mock import AsyncMock
 from uuid import UUID, uuid4
 
 import pytest
 
 from app.services.agent_runtime_service import AgentRuntimeService, AgentTaskCancelled
+from app.repositories.agent_task_repository import AgentTaskRepository
 
 
 class FakeAsyncSession:
     def __init__(self, authoritative_status: dict[UUID, str]) -> None:
         self.authoritative_status = authoritative_status
         self.commit_calls = 0
+        self.rollback_calls = 0
 
     async def refresh(self, instance: object) -> None:
         task_id = getattr(instance, "id", None)
         if task_id in self.authoritative_status:
             setattr(instance, "status", self.authoritative_status[task_id])
 
     async def commit(self) -> None:
         self.commit_calls += 1
 
+    async def rollback(self) -> None:
+        self.rollback_calls += 1
+
     async def get(self, model: object, identity: UUID) -> object | None:  # noqa: ARG002
         return None
 
 
 class FakeTaskRepository:
     def __init__(self, task: SimpleNamespace) -> None:
         self.task = task
         self.update_calls: list[dict[str, object]] = []
 
     async def get_by_id(self, task_id: UUID) -> SimpleNamespace | None:
@@ -43,20 +49,53 @@ class FakeTaskRepository:
     async def get_step_by_tool_call(self, task_id: UUID, tool_call_id: str) -> None:  # noqa: ARG002
         return None
 
     async def list_steps(self, task_id: UUID) -> list[object]:  # noqa: ARG002
         return []
 
     async def create_dynamic_step(self, **kwargs: object) -> object:
         raise AssertionError("cancelled tasks must not create dynamic steps")
 
 
+class ClaimTaskRepository(FakeTaskRepository):
+    def __init__(self, task: SimpleNamespace, *, claim_succeeds: bool) -> None:
+        super().__init__(task)
+        self.claim_succeeds = claim_succeeds
+        self.claim_calls = 0
+
+    async def claim_queued_task(self, task_id: UUID, started_at: object) -> bool:  # noqa: ARG002
+        self.claim_calls += 1
+        return self.claim_succeeds
+
+
+class DurationTaskRepository(FakeTaskRepository):
+    def __init__(self, task: SimpleNamespace, step: SimpleNamespace) -> None:
+        super().__init__(task)
+        self.step = step
+        self.step_update_calls: list[dict[str, object]] = []
+
+    async def get_step_by_tool_call(
+        self,
+        task_id: UUID,
+        tool_call_id: str,
+    ) -> SimpleNamespace | None:
+        if task_id == self.task.id and tool_call_id == self.step.tool_call_id:
+            return self.step
+        return None
+
+    async def update_step(self, step: SimpleNamespace, **values: object) -> SimpleNamespace:
+        self.step_update_calls.append(values)
+        for key, value in values.items():
+            setattr(step, key, value)
+        return step
+
+
 class FakeConversationRepository:
     def __init__(self) -> None:
         self.events: list[dict[str, object]] = []
         self.messages: list[dict[str, object]] = []
 
     async def add_event(
         self,
         *,
         task_id: UUID,
         conversation_id: UUID | None,
@@ -73,20 +112,23 @@ class FakeConversationRepository:
         )
         return SimpleNamespace(sequence_no=len(self.events))
 
     async def add_message(self, **kwargs: object) -> SimpleNamespace:
         self.messages.append(kwargs)
         return SimpleNamespace()
 
     async def get_for_user(self, conversation_id: UUID, user_id: UUID) -> SimpleNamespace:  # noqa: ARG002
         return SimpleNamespace(id=conversation_id)
 
+    async def list_messages(self, conversation_id: UUID, limit: int = 80) -> list[SimpleNamespace]:  # noqa: ARG002
+        return []
+
 
 class FakeBroker:
     def __init__(self) -> None:
         self.published: list[tuple[UUID, str, dict[str, object]]] = []
 
     async def publish(self, task_id: UUID, event_type: str, payload: dict[str, object]) -> None:
         self.published.append((task_id, event_type, payload))
 
 
 def _build_task(*, status: str = "running") -> SimpleNamespace:
@@ -108,20 +150,31 @@ def _build_service(task: SimpleNamespace) -> tuple[AgentRuntimeService, FakeTask
     db = FakeAsyncSession({task.id: "cancelled"})
     tasks = FakeTaskRepository(task)
     conversations = FakeConversationRepository()
     broker = FakeBroker()
     service = AgentRuntimeService(db, broker=broker)
     service.tasks = tasks
     service.conversations = conversations
     return service, tasks, conversations, broker
 
 
+def build_runtime_service_for_claim(
+    claim_succeeds: bool,
+) -> tuple[AgentRuntimeService, SimpleNamespace]:
+    task = _build_task(status="queued")
+    db = FakeAsyncSession({task.id: "queued"})
+    service = AgentRuntimeService(db, broker=FakeBroker())
+    service.tasks = ClaimTaskRepository(task, claim_succeeds=claim_succeeds)
+    service.conversations = FakeConversationRepository()
+    return service, task
+
+
 @pytest.mark.asyncio
 async def test_record_event_does_not_turn_cancelled_task_into_succeeded(
 ) -> None:
     task = _build_task()
     service, tasks, conversations, broker = _build_service(task)
 
     with pytest.raises(AgentTaskCancelled):
         await service._record_event(
             task,
             registry=SimpleNamespace(),
@@ -246,10 +299,154 @@ async def test_finish_task_compensates_when_grounded_postprocess_was_skipped(
 async def test_mark_failed_does_not_turn_cancelled_task_into_failed() -> None:
     task = _build_task()
     service, tasks, conversations, broker = _build_service(task)
 
     await service._mark_failed(task, RuntimeError("late failure"))
 
     assert task.status == "cancelled"
     assert tasks.update_calls == []
     assert conversations.events == []
     assert broker.published == []
+
+
+@pytest.mark.asyncio
+async def test_execute_skips_graph_when_claim_is_owned(
+    monkeypatch: pytest.MonkeyPatch,
+) -> None:
+    service, task = build_runtime_service_for_claim(False)
+    graph_run = AsyncMock()
+    monkeypatch.setattr("app.services.agent_runtime_service.LearningAgentGraph.run", graph_run)
+
+    assert await service.execute(task.id) == {"status": "already_claimed"}
+    graph_run.assert_not_awaited()
+
+
+@pytest.mark.asyncio
+async def test_execute_rolls_back_before_recording_runtime_failure(
+    monkeypatch: pytest.MonkeyPatch,
+) -> None:
+    service, task = build_runtime_service_for_claim(True)
+    marked_failed = AsyncMock()
+
+    async def assert_rollback_then_mark_failed(*args: object) -> None:
+        assert service.db.rollback_calls == 1
+
+    marked_failed.side_effect = assert_rollback_then_mark_failed
+    monkeypatch.setattr(service, "_get_user", AsyncMock(return_value=SimpleNamespace(id=task.user_id)))
+    monkeypatch.setattr(service, "_mark_failed", marked_failed)
+    monkeypatch.setattr(
+        "app.services.agent_runtime_service.AsyncPostgresSaver.from_conn_string",
+        lambda _: _FakeCheckpointerContext(),
+    )
+    graph_run = AsyncMock(side_effect=RuntimeError("graph failed"))
+
+    class FailingGraph:
+        def __init__(self, **kwargs: object) -> None:  # noqa: ARG002
+            self.run = graph_run
+
+    monkeypatch.setattr("app.services.agent_runtime_service.LearningAgentGraph", FailingGraph)
+
+    with pytest.raises(RuntimeError, match="graph failed"):
+        await service.execute(task.id)
+
+    marked_failed.assert_awaited_once()
+
+
+@pytest.mark.asyncio
+async def test_execute_commits_before_graph_resume(
+    monkeypatch: pytest.MonkeyPatch,
+) -> None:
+    service, task = build_runtime_service_for_claim(True)
+    monkeypatch.setattr(service, "_get_user", AsyncMock(return_value=SimpleNamespace(id=task.user_id)))
+    monkeypatch.setattr(service, "_finish_task", AsyncMock())
+    monkeypatch.setattr(
+        "app.services.agent_runtime_service.AsyncPostgresSaver.from_conn_string",
+        lambda _: _FakeCheckpointerContext(),
+    )
+
+    class ResumingGraph:
+        def __init__(self, **kwargs: object) -> None:  # noqa: ARG002
+            pass
+
+        async def resume(self, *, thread_id: str, approved: bool) -> dict[str, object]:  # noqa: ARG002
+            assert service.db.commit_calls >= 2
+            return {"status": "completed"}
+
+    monkeypatch.setattr("app.services.agent_runtime_service.LearningAgentGraph", ResumingGraph)
+
+    assert await service.execute(task.id, approved=True) == {"status": "completed"}
+
+
+@pytest.mark.asyncio
+async def test_execute_setup_failure_rolls_back_and_marks_claimed_task_failed(
+    monkeypatch: pytest.MonkeyPatch,
+) -> None:
+    service, task = build_runtime_service_for_claim(True)
+    marked_failed = AsyncMock()
+
+    async def assert_rollback_then_mark_failed(*args: object) -> None:
+        assert service.db.rollback_calls == 1
+
+    marked_failed.side_effect = assert_rollback_then_mark_failed
+    monkeypatch.setattr(service, "_get_user", AsyncMock(side_effect=RuntimeError("user load failed")))
+    monkeypatch.setattr(service, "_mark_failed", marked_failed)
+
+    with pytest.raises(RuntimeError, match="user load failed"):
+        await service.execute(task.id)
+
+    marked_failed.assert_awaited_once()
+
+
+@pytest.mark.asyncio
+async def test_tool_completed_event_persists_duration_to_matching_step() -> None:
+    task = _build_task(status="running")
+    step = SimpleNamespace(tool_call_id="timed-call")
+    service = AgentRuntimeService(FakeAsyncSession({task.id: "running"}), broker=FakeBroker())
+    tasks = DurationTaskRepository(task, step)
+    service.tasks = tasks
+    service.conversations = FakeConversationRepository()
+
+    await service._record_event(
+        task,
+        registry=SimpleNamespace(),
+        event_type="tool_completed",
+        state={},
+        payload={"tool_call_id": "timed-call", "duration_ms": 27},
+    )
+
+    assert tasks.step_update_calls == [{"duration_ms": 27}]
+
+
+@pytest.mark.asyncio
+async def test_claim_queued_task_uses_queued_langgraph_conditional_update() -> None:
+    class CapturingSession:
+        def __init__(self) -> None:
+            self.statement = None
+
+        async def execute(self, statement):
+            self.statement = statement
+            return SimpleNamespace(rowcount=1)
+
+    session = CapturingSession()
+    task_id = uuid4()
+    started_at = datetime.now(UTC)
+
+    assert await AgentTaskRepository(session).claim_queued_task(task_id, started_at) is True
+
+    compiled = session.statement.compile()
+    statement = str(session.statement)
+    assert "UPDATE agent_tasks" in statement
+    assert "agent_tasks.status = :status_1" in statement
+    assert "agent_tasks.runtime_mode = :runtime_mode_1" in statement
+    assert task_id in compiled.params.values()
+    assert "queued" in compiled.params.values()
+    assert "langgraph" in compiled.params.values()
+    assert "running" in compiled.params.values()
+    assert started_at in compiled.params.values()
+
+
+class _FakeCheckpointerContext:
+    async def __aenter__(self) -> object:
+        return object()
+
+    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:  # noqa: ARG002
+        return None
diff --git a/backend/tests/test_agent_runtime.py b/backend/tests/test_agent_runtime.py
index 641b154..b22df67 100644
--- a/backend/tests/test_agent_runtime.py
+++ b/backend/tests/test_agent_runtime.py
@@ -1,39 +1,341 @@
 from __future__ import annotations
 
 from pathlib import Path
 from types import SimpleNamespace
+from unittest.mock import AsyncMock
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
+from app.services.agent_runtime_service import AgentRuntimeService
 
 
 class QueryInput(SimpleNamespace):
     pass
 
 
+def schema(name: str) -> dict[str, object]:
+    return {
+        "type": "function",
+        "function": {"name": name, "parameters": {"type": "object"}},
+    }
+
+
+EXPECTED_LEARNING_TOOL_NAMES = {
+    "search_course_knowledge",
+    "search_web",
+    "answer_course_question",
+    "generate_learning_path",
+    "generate_explanation",
+    "generate_quiz",
+    "parse_uploaded_document",
+    "generate_mindmap",
+    "generate_diagram",
+    "transcribe_audio",
+    "synthesize_speech",
+    "analyze_learning_diagnosis",
+    "refresh_recommendations",
+    "update_profile_from_dialogue",
+    "rebuild_profile",
+    "reflect_learning_memory",
+    "review_artifacts",
+    "review_multimodal_asset",
+    "apply_evolution_strategy",
+    "generate_educational_image",
+    "generate_immersive_classroom",
+    "generate_lesson_video",
+    "generate_storyboard_html",
+    "generate_interactive_courseware",
+}
+
+
+EXPECTED_LEARNING_TOOL_CONTRACTS = {
+    "analyze_learning_diagnosis": ("DiagnosisAgent", True, "low", False, 120, {"type": "object", "properties": {}, "required": [], "additionalProperties": False}),
+    "answer_course_question": ("TutorAgent", True, "low", False, 120, {"type": "object", "properties": {"question": {"type": "string"}, "top_k": {"type": "integer", "minimum": 1, "maximum": 20}}, "required": ["question"], "additionalProperties": False}),
+    "apply_evolution_strategy": ("EvolutionAgent", True, "high", True, 120, {"type": "object", "properties": {"strategy_id": {"type": "string"}}, "required": [], "additionalProperties": False}),
+    "generate_diagram": ("KnowledgeAgent", True, "low", False, 120, {"type": "object", "properties": {"concept": {"type": "string", "description": "需要图解的概念"}, "diagram_type": {"type": "string", "enum": ["flowchart", "sequence", "class", "er"]}}, "required": ["concept"], "additionalProperties": False}),
+    "generate_educational_image": ("VisualResourceAgent", True, "low", False, 180, {"type": "object", "properties": {"topic": {"type": "string", "minLength": 1}, "image_type": {"type": "string", "enum": ["concept_illustration", "process_visual", "analogy", "cover", "summary_card"]}, "style": {"type": "string"}, "size": {"type": "string", "enum": ["1024x1024", "1280x720", "720x1280", "1024x768"]}, "requirement": {"type": "string"}}, "required": ["topic"], "additionalProperties": False}),
+    "generate_explanation": ("ResourceAgent", True, "low", False, 120, {"type": "object", "properties": {"topic": {"type": "string"}, "resource_type": {"type": "string", "enum": ["explanation", "summary", "example", "flashcard", "review"]}, "requirement": {"type": "string"}}, "required": ["topic"], "additionalProperties": False}),
+    "generate_immersive_classroom": ("ImmersiveClassroomAgent", True, "low", False, 30, {"type": "object", "properties": {"topic": {"type": "string", "minLength": 1}, "learning_goal": {"type": "string"}, "generate_video_export": {"type": "boolean"}, "enable_images": {"type": "boolean"}, "enable_video_clips": {"type": "boolean"}, "enable_tts": {"type": "boolean"}}, "required": ["topic"], "additionalProperties": False}),
+    "generate_interactive_courseware": ("CoursewareAgent", True, "low", False, 180, {"type": "object", "properties": {"topic": {"type": "string", "minLength": 1}, "interaction_type": {"type": "string", "enum": ["stepper", "drag_sort", "quiz_simulation", "graph_traversal", "timeline"]}, "target_level": {"type": "string"}, "requirement": {"type": "string"}}, "required": ["topic"], "additionalProperties": False}),
+    "generate_learning_path": ("PlannerAgent", True, "low", False, 120, {"type": "object", "properties": {"goal": {"type": "string"}}, "required": ["goal"], "additionalProperties": False}),
+    "generate_lesson_video": ("VideoResourceAgent", True, "low", False, 30, {"type": "object", "properties": {"topic": {"type": "string", "minLength": 1}, "duration_seconds": {"type": "integer", "minimum": 30, "maximum": 240}, "visual_mode": {"type": "string", "enum": ["storyboard", "animated_diagram", "t2v_broll", "mixed"]}, "voice": {"type": "string"}, "target_level": {"type": "string"}}, "required": ["topic"], "additionalProperties": False}),
+    "generate_mindmap": ("KnowledgeAgent", True, "low", False, 120, {"type": "object", "properties": {"topic": {"type": "string", "description": "知识主题"}, "scope": {"type": "string", "enum": ["course", "chapter", "custom"]}, "depth": {"type": "integer", "minimum": 2, "maximum": 5}}, "required": ["topic"], "additionalProperties": False}),
+    "generate_quiz": ("QuizAgent", True, "low", False, 120, {"type": "object", "properties": {"topic": {"type": "string"}, "count": {"type": "integer", "minimum": 1, "maximum": 20}, "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]}, "question_types": {"type": "array", "items": {"type": "string"}}}, "required": ["topic"], "additionalProperties": False}),
+    "generate_storyboard_html": ("VideoResourceAgent", True, "low", False, 120, {"type": "object", "properties": {"topic": {"type": "string", "minLength": 1}, "duration_seconds": {"type": "integer", "minimum": 30, "maximum": 240}, "requirement": {"type": "string"}}, "required": ["topic"], "additionalProperties": False}),
+    "parse_uploaded_document": ("KnowledgeAgent", True, "low", False, 120, {"type": "object", "properties": {"material_id": {"type": "string", "description": "课程资料 UUID"}}, "required": ["material_id"], "additionalProperties": False}),
+    "rebuild_profile": ("ProfileAgent", True, "low", False, 120, {"type": "object", "properties": {}, "required": [], "additionalProperties": False}),
+    "reflect_learning_memory": ("MemoryAgent", True, "low", False, 120, {"type": "object", "properties": {}, "required": [], "additionalProperties": False}),
+    "refresh_recommendations": ("RecommendAgent", True, "low", False, 120, {"type": "object", "properties": {}, "required": [], "additionalProperties": False}),
+    "review_artifacts": ("ReviewAgent", False, "low", False, 120, {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"], "additionalProperties": False}),
+    "review_multimodal_asset": ("ReviewAgent", False, "low", False, 120, {"type": "object", "properties": {"asset_id": {"type": "string", "minLength": 1}}, "required": ["asset_id"], "additionalProperties": False}),
+    "search_course_knowledge": ("KnowledgeAgent", False, "low", False, 120, {"type": "object", "properties": {"query": {"type": "string"}, "top_k": {"type": "integer", "minimum": 1, "maximum": 20}}, "required": ["query"], "additionalProperties": False}),
+    "search_web": ("KnowledgeAgent", False, "low", False, 45, {"type": "object", "properties": {"query": {"type": "string", "description": "搜索关键词或完整问题"}, "max_results": {"type": "integer", "minimum": 1, "maximum": 10}, "domain": {"type": "string", "description": "可选垂直领域，如 general/academic/code/finance"}}, "required": ["query"], "additionalProperties": False}),
+    "synthesize_speech": ("TutorAgent", False, "low", False, 120, {"type": "object", "properties": {"text": {"type": "string", "description": "要转换的文字"}, "model_type": {"type": "string", "enum": ["tts", "voiceclone", "voicedesign"]}, "voice": {"type": "string", "description": "音色，可由具体 Provider 解释"}, "speed": {"type": "number", "minimum": 0.5, "maximum": 2.0}, "response_format": {"type": "string", "enum": ["wav", "mp3"]}}, "required": ["text"], "additionalProperties": False}),
+    "transcribe_audio": ("TutorAgent", False, "low", False, 60, {"type": "object", "properties": {"audio_base64": {"type": "string", "description": "Base64 编码的音频数据"}, "filename": {"type": "string", "description": "文件名（用于推断格式）"}, "language": {"type": "string", "description": "语言代码，默认 zh"}}, "required": ["audio_base64"], "additionalProperties": False}),
+    "update_profile_from_dialogue": ("ProfileAgent", True, "low", False, 120, {"type": "object", "properties": {"dialogue_text": {"type": "string"}, "source_message_id": {"type": "string"}}, "required": ["dialogue_text"], "additionalProperties": False}),
+}
+
+
+def test_learning_registry_keeps_public_tool_contracts() -> None:
+    from app.agent_runtime.toolsets import (
+        register_knowledge_tools,
+        register_learning_tools,
+        register_media_tools,
+        register_profile_tools,
+        register_review_tools,
+    )
+
+    registry = build_learning_tool_registry(SimpleNamespace(), SimpleNamespace(id=uuid4()))
+    assert set(EXPECTED_LEARNING_TOOL_CONTRACTS) == EXPECTED_LEARNING_TOOL_NAMES
+    assert {item["function"]["name"] for item in registry.tool_schemas()} == EXPECTED_LEARNING_TOOL_NAMES
+    for name, (agent_name, writes_db, risk_level, requires_confirmation, timeout_seconds, input_schema) in EXPECTED_LEARNING_TOOL_CONTRACTS.items():
+        tool = registry.get(name)
+        assert tool.agent_name == agent_name
+        assert tool.writes_db is writes_db
+        assert tool.risk_level == risk_level
+        assert tool.requires_confirmation is requires_confirmation
+        assert tool.timeout_seconds == timeout_seconds
+        assert tool.input_schema == input_schema
+    assert all(
+        callable(register_toolset)
+        for register_toolset in (
+            register_knowledge_tools,
+            register_learning_tools,
+            register_profile_tools,
+            register_review_tools,
+            register_media_tools,
+        )
+    )
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
+def test_fallback_excludes_skipped_tools() -> None:
+    tools = [schema(name) for name in ("generate_quiz", "search_web")]
+
+    selected = select_tool_schemas(
+        {
+            "goal": "随便聊聊",
+            "tool_hints": [],
+            "skip_tools": ["generate_quiz"],
+        },
+        tools,
+    )
+
+    assert [item["function"]["name"] for item in selected] == ["search_web"]  # type: ignore[index]
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
+    assert isinstance(plan_payload["supervisor_duration_ms"], int)
+    assert plan_payload["supervisor_duration_ms"] >= 0
+
+
+@pytest.mark.asyncio
+async def test_non_candidate_tool_call_is_not_executed_from_full_registry() -> None:
+    class NonCandidateToolProvider:
+        def __init__(self) -> None:
+            self.calls = 0
+
+        async def chat(self, messages, **kwargs):
+            self.calls += 1
+            if self.calls == 1:
+                return ChatResponse(
+                    content="",
+                    finish_reason="tool_calls",
+                    tool_calls=[ToolCall(id="non-candidate-quiz", name="generate_quiz", arguments={"topic": "栈"})],
+                )
+            return ChatResponse(content='{"status":"complete","summary":"已完成","final_answer":"栈是后进先出。"}')
+
+    executed_quiz = False
+    executed_search = False
+
+    async def search_handler(context: ToolContext, arguments: dict[str, object]) -> ToolExecutionResult:
+        nonlocal executed_search
+        executed_search = True
+        return ToolExecutionResult(output={"query": arguments["query"]})
+
+    async def quiz_handler(context: ToolContext, arguments: dict[str, object]) -> ToolExecutionResult:
+        nonlocal executed_quiz
+        executed_quiz = True
+        return ToolExecutionResult(output={"quiz": "unexpected"})
+
+    registry = ToolRegistry()
+    registry.register(
+        AgentTool(
+            name="search_course_knowledge",
+            description="检索课程资料",
+            agent_name="KnowledgeAgent",
+            input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
+            handler=search_handler,
+        )
+    )
+    registry.register(
+        AgentTool(
+            name="answer_course_question",
+            description="课程答疑",
+            agent_name="TutorAgent",
+            input_schema={"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
+            handler=search_handler,
+        )
+    )
+    registry.register(
+        AgentTool(
+            name="generate_quiz",
+            description="生成练习",
+            agent_name="QuizAgent",
+            input_schema={"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]},
+            handler=quiz_handler,
+        )
+    )
+
+    provider = NonCandidateToolProvider()
+    result = await LearningAgentGraph(
+        registry=registry,
+        supervisor=MiMoSupervisor(provider=provider),
+    ).run(
+        task_id=uuid4(),
+        conversation_id=uuid4(),
+        user_id=uuid4(),
+        course_id=uuid4(),
+        goal="解释栈",
+        thread_id="non-candidate-tool-call",
+        skip_tools=["answer_course_question"],
+    )
+
+    assert result["status"] == "completed"
+    assert executed_quiz is False
+    assert executed_search is True
+    assert provider.calls == 2
+    assert all(call["name"] != "generate_quiz" for call in result["tool_calls"])
+    assert [call["name"] for call in result["tool_calls"]] == ["search_course_knowledge"]
+
+
 def test_explicit_course_source_qa_plans_only_grounded_answer() -> None:
     from app.agent_runtime.supervisor_intents import plan_required_tools
 
     assert plan_required_tools(
         "基于课程资料解释栈并给出引用",
         is_profile_update_only=False,
     ) == ["answer_course_question"]
 
 
 def test_web_search_qa_does_not_fall_through_to_course_grounded_answer() -> None:
@@ -132,20 +434,78 @@ async def test_answer_tool_final_answer_bypasses_second_supervisor_call() -> Non
         user_id=uuid4(),
         course_id=uuid4(),
         goal="解释栈",
         thread_id="grounded-pass-through",
     )
 
     assert result["final_answer"] == "栈是 LIFO [S1]。"
     assert supervisor.calls == 1
 
 
+@pytest.mark.asyncio
+async def test_tool_completed_event_has_duration_ms() -> None:
+    class OneToolSupervisor:
+        async def decide(self, state, tool_schemas):
+            if state.get("observations"):
+                return AgentDecision(status="complete", summary="完成", final_answer="栈是后进先出。")
+            return AgentDecision(
+                status="continue",
+                summary="查询课程知识",
+                tool_calls=[
+                    PlannedToolCall(
+                        id="tool-duration-call",
+                        name="search_course_knowledge",
+                        arguments={"query": "栈"},
+                    )
+                ],
+            )
+
+    async def handler(context: ToolContext, arguments: dict[str, object]) -> ToolExecutionResult:
+        return ToolExecutionResult(output={"query": arguments["query"]})
+
+    events: list[tuple[str, dict[str, object]]] = []
+
+    async def event_sink(event_type, state, payload):
+        events.append((event_type, payload))
+
+    registry = ToolRegistry()
+    registry.register(
+        AgentTool(
+            name="search_course_knowledge",
+            description="检索课程知识库",
+            agent_name="KnowledgeAgent",
+            input_schema={
+                "type": "object",
+                "properties": {"query": {"type": "string"}},
+                "required": ["query"],
+            },
+            handler=handler,
+        )
+    )
+    await LearningAgentGraph(
+        registry=registry,
+        supervisor=OneToolSupervisor(),
+        event_sink=event_sink,
+    ).run(
+        task_id=uuid4(),
+        conversation_id=uuid4(),
+        user_id=uuid4(),
+        course_id=uuid4(),
+        goal="解释栈",
+        thread_id="tool-duration",
+    )
+
+    payload = next(payload for kind, payload in events if kind == "tool_completed")
+    assert isinstance(payload["duration_ms"], int)
+    assert payload["duration_ms"] >= 0
+
+
 def test_agent_runtime_no_longer_extracts_dialogue_synchronously() -> None:
     source = (Path(__file__).resolve().parents[1] / "app/services/agent_runtime_service.py").read_text(
         encoding="utf-8"
     )
     assert "extract_knowledge_from_dialogue(" not in source
 
 
 @pytest.mark.asyncio
 async def test_answer_tool_reuses_grounded_pipeline_without_conversation_messages(monkeypatch) -> None:
     from app.schemas.tutor import TutorChatResponse
@@ -308,20 +668,67 @@ async def test_result_saver_failure_does_not_rerun_committed_tool() -> None:
         "answer_course_question",
         {},
         ToolContext(task_id=uuid4(), tool_call_id="qa-save-fail", user_id=uuid4(), course_id=uuid4()),
     )
 
     assert result.success is True
     assert result.final_answer == "已提交回答"
     assert handler_calls == 1
 
 
+@pytest.mark.asyncio
+async def test_failed_database_tool_rolls_back_before_runtime_saves_failed_step() -> None:
+    class StepRepository:
+        def __init__(self, task_id: object, step: SimpleNamespace) -> None:
+            self.task_id = task_id
+            self.step = step
+            self.update_calls: list[dict[str, object]] = []
+
+        async def get_step_by_tool_call(self, task_id: object, tool_call_id: str):
+            if task_id == self.task_id and tool_call_id == self.step.tool_call_id:
+                return self.step
+            return None
+
+        async def update_step(self, step: SimpleNamespace, **values: object) -> SimpleNamespace:
+            self.update_calls.append(values)
+            for key, value in values.items():
+                setattr(step, key, value)
+            return step
+
+    task_id = uuid4()
+    step = SimpleNamespace(tool_call_id="failed-write")
+    db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
+    service = AgentRuntimeService(db)  # type: ignore[arg-type]
+    steps = StepRepository(task_id, step)
+    service.tasks = steps  # type: ignore[assignment]
+    registry = build_learning_tool_registry(
+        db,
+        SimpleNamespace(id=uuid4(), role="student"),
+        result_saver=service._save_tool_result,
+    )
+
+    async def failed_write(context: ToolContext, arguments: dict[str, object]) -> ToolExecutionResult:
+        raise RuntimeError("database write failed")
+
+    registry.get("generate_quiz").handler = failed_write
+    result = await registry.execute(
+        "generate_quiz",
+        {"topic": "栈"},
+        ToolContext(task_id=task_id, tool_call_id="failed-write", user_id=uuid4(), course_id=uuid4()),
+    )
+
+    assert result.success is False
+    db.rollback.assert_awaited_once()
+    assert steps.update_calls
+    assert steps.update_calls[-1]["status"] == "failed"
+
+
 @pytest.mark.asyncio
 async def test_tool_registry_rejects_unknown_and_high_risk_tools() -> None:
     async def handler(context: ToolContext, arguments: dict[str, object]) -> ToolExecutionResult:
         return ToolExecutionResult(output={"ok": True})
 
     registry = ToolRegistry()
     registry.register(
         AgentTool(
             name="apply_evolution_strategy",
             description="应用自进化策略",
@@ -573,21 +980,21 @@ class StructuredDecisionProvider:
                 '"tool_calls":[{"tool_name":"search_course_knowledge",'
                 '"parameters":{"query":"栈","top_k":5}}]}'
             )
         )
 
 
 @pytest.mark.asyncio
 async def test_mimo_supervisor_parses_structured_tool_fallback_without_exposing_thoughts() -> None:
     decision = await MiMoSupervisor(provider=StructuredDecisionProvider()).decide(
         {"goal": "解释栈", "messages": [], "observations": [], "artifacts": []},
-        [],
+        [schema("search_course_knowledge")],
     )
 
     assert decision.status == "continue"
     assert decision.summary == "先检索课程资料"
     assert decision.tool_calls[0].name == "search_course_knowledge"
     assert decision.tool_calls[0].arguments == {"query": "栈", "top_k": 5}
     assert "private" not in decision.summary
 
 
 class DirectUngroundedAnswerProvider:
@@ -842,21 +1249,21 @@ async def test_mimo_supervisor_routes_explicit_strategy_apply_to_high_risk_tool(
     )
 
     assert decision.status == "continue"
     assert decision.tool_calls[0].name == "apply_evolution_strategy"
 
 
 @pytest.mark.asyncio
 async def test_mimo_supervisor_fills_safe_arguments_for_selected_tool() -> None:
     decision = await MiMoSupervisor(provider=EmptyArgumentToolProvider()).decide(
         {"goal": "请检索二叉树资料", "messages": [], "observations": [], "tool_calls": []},
-        [],
+        [schema("search_course_knowledge")],
     )
 
     assert decision.tool_calls[0].arguments["query"] == "检索二叉树资料"
 
 
 def test_mimo_supervisor_normalizes_status_tool_args_shape() -> None:
     supervisor = MiMoSupervisor(provider=StructuredDecisionProvider())
 
     decision = supervisor._parse_decision(
         '{"status":"continue","summary":"先检索",'
@@ -1003,21 +1410,21 @@ def test_default_learning_tool_registry_exposes_specialized_agents_and_risk_boun
         "generate_mindmap",
         "generate_diagram",
         "transcribe_audio",
         "synthesize_speech",
     }.issubset(names)
     assert registry.requires_confirmation("apply_evolution_strategy") is True
     assert registry.risk_level("apply_evolution_strategy") == "high"
 
 
 def test_generate_explanation_artifact_refs_keep_resource_type_for_frontend_categories() -> None:
-    source = (Path(__file__).resolve().parents[1] / "app/agent_runtime/service_tools.py").read_text(
+    source = (Path(__file__).resolve().parents[1] / "app/agent_runtime/toolsets/learning_tools.py").read_text(
         encoding="utf-8"
     )
 
     assert '"resource_type": data.get("resource_type")' in source
     assert '"resource_id": str(result.resource_id)' in source
 
 
 def test_parse_uploaded_document_requires_explicit_material_id_and_is_not_faked_by_supervisor() -> None:
     user = SimpleNamespace(id=uuid4(), role="student")
     registry = build_learning_tool_registry(SimpleNamespace(), user)  # type: ignore[arg-type]
diff --git a/backend/tests/test_real_provider_acceptance_helpers.py b/backend/tests/test_real_provider_acceptance_helpers.py
new file mode 100644
index 0000000..3db1aeb
--- /dev/null
+++ b/backend/tests/test_real_provider_acceptance_helpers.py
@@ -0,0 +1,23 @@
+from __future__ import annotations
+
+import unittest
+
+from scripts.real_provider_acceptance import (
+    classify_provider,
+    require_real_response,
+    sanitize_error,
+)
+
+
+class RealProviderAcceptanceHelperTests(unittest.TestCase):
+    def test_classify_provider_rejects_mock_and_fallback(self) -> None:
+        self.assertEqual(classify_provider({"provider": "xiaomi_mimo", "fallback_used": False}), "real")
+        self.assertEqual(classify_provider({"provider": "mock", "fallback_used": False}), "mock")
+        self.assertEqual(classify_provider({"provider": "fallback", "fallback_used": True}), "fallback")
+
+    def test_require_real_response_rejects_mock_even_when_http_succeeds(self) -> None:
+        with self.assertRaisesRegex(RuntimeError, "tutor"):
+            require_real_response({"provider": "mock", "fallback_used": False}, "tutor")
+
+    def test_sanitize_error_removes_bearer_tokens(self) -> None:
+        self.assertNotIn("secret-value", sanitize_error("Bearer secret-value provider failed"))
diff --git a/backend/tests/test_structured_output_normalization.py b/backend/tests/test_structured_output_normalization.py
new file mode 100644
index 0000000..ca65962
--- /dev/null
+++ b/backend/tests/test_structured_output_normalization.py
@@ -0,0 +1,35 @@
+from __future__ import annotations
+
+import unittest
+
+from app.agents.structured_outputs import EvolutionAnalysisOutput, MemoryReflectOutput, ReviewOutput
+
+
+class StructuredOutputNormalizationTests(unittest.TestCase):
+    def test_memory_evidence_string_is_normalized_to_list(self) -> None:
+        output = MemoryReflectOutput.model_validate(
+            {"memories": [{"content": "循环队列薄弱", "evidence": "quiz_id=abc"}]}
+        )
+        self.assertEqual(output.memories[0].evidence, ["quiz_id=abc"])
+
+    def test_flat_evolution_output_is_wrapped_as_one_strategy(self) -> None:
+        output = EvolutionAnalysisOutput.model_validate(
+            {
+                "change_summary": "增加循环队列练习",
+                "before_snapshot": {"difficulty": "medium"},
+                "after_snapshot": {"difficulty": "easy"},
+                "risk_level": "low",
+                "evidence": "quiz wrong",
+            }
+        )
+        self.assertEqual(len(output.strategies), 1)
+        self.assertEqual(output.strategies[0].change_summary, "增加循环队列练习")
+
+    def test_review_issue_objects_are_normalized_to_descriptions(self) -> None:
+        output = ReviewOutput.model_validate(
+            {
+                "pass": False,
+                "issues": [{"type": "知识偏离", "description": "缺少可靠来源", "severity": "high"}],
+            }
+        )
+        self.assertEqual(output.issues, ["知识偏离：缺少可靠来源"])
diff --git a/backend/tests/test_supervisor_intents.py b/backend/tests/test_supervisor_intents.py
index 0d4e0d5..7820ba1 100644
--- a/backend/tests/test_supervisor_intents.py
+++ b/backend/tests/test_supervisor_intents.py
@@ -1,28 +1,61 @@
 """Supervisor 意图路由回归测试 — 防止工具误匹配。"""
 
 from __future__ import annotations
 
 import pytest
 
 from app.agent_runtime import supervisor_intents
+from app.agent_runtime.supervisor_completion import format_search_output_answer
+from app.agent_runtime.supervisor_policy import safe_arguments
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
+def test_safe_arguments_compatibility_for_courseware_ppt_goal() -> None:
+    goal = "请做一份二叉树讲解 PPT"
+
+    expected = safe_arguments("generate_interactive_courseware", {}, goal)
+    actual = MiMoSupervisor(provider=object())._safe_arguments(
+        "generate_interactive_courseware", {}, goal
+    )
+
+    assert actual == expected
+    assert actual["topic"] == expected["topic"]
+    assert actual["interaction_type"] == "stepper"
+
+
+@pytest.mark.asyncio
+async def test_profile_only_decision_keeps_original_plan_text() -> None:
+    decision = await MiMoSupervisor(provider=object()).decide(
+        {"goal": "我是软件工程大二学生，递归比较薄弱，请记住我的学习偏好。", "observations": [], "messages": []},
+        [{"type": "function", "function": {"name": "update_profile_from_dialogue"}}],
+    )
+
+    assert decision.summary == "本轮仅更新对话式学习画像，不扩张为资源或练习生成任务。"
+    assert decision.plan == ["从当前对话提取并更新学习画像"]
+    assert decision.tool_calls[0].name == "update_profile_from_dialogue"
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
diff --git "a/docs/19_\346\265\213\350\257\225\346\226\271\346\241\210/25_\347\234\237\345\256\236Provider\345\205\250\351\207\217\351\252\214\346\224\266\350\256\260\345\275\225.md" "b/docs/19_\346\265\213\350\257\225\346\226\271\346\241\210/25_\347\234\237\345\256\236Provider\345\205\250\351\207\217\351\252\214\346\224\266\350\256\260\345\275\225.md"
new file mode 100644
index 0000000..7538a7f
--- /dev/null
+++ "b/docs/19_\346\265\213\350\257\225\346\226\271\346\241\210/25_\347\234\237\345\256\236Provider\345\205\250\351\207\217\351\252\214\346\224\266\350\256\260\345\275\225.md"
@@ -0,0 +1,88 @@
+# 25_真实 Provider 全量验收记录
+
+> 记录状态：**验收基线尚未建立；本文件仅记录当前可核验的 Runner 准备度和复验边界。**
+>
+> 建立日期：2026-07-12
+> 适用范围：文本 LLM 与外部媒体 Provider 的全量、真实 Provider 验收，不替代 Mock 测试或既有真实 LLM 主链路专项。
+
+## 结论
+
+当前工作区没有可核验的真实 Provider 全量验收 JSON、逐场景通过矩阵、延迟或产物 ID。因此本记录中不存在任何全量通过结论，也没有将 Mock、fallback 或未配置能力计为通过。
+
+`scripts/real_provider_acceptance.py` 当前提供并已测试 Provider 分类、真实响应拒绝和错误脱敏辅助函数；它**尚未**提供计划中的命令行入口、Provider 预检、认证 API 场景执行、轮询、JSON 输出或逐场景结果汇总。故当前不能以该文件执行真实 Provider 全量基线，也不能从其进程退出码推导出验收结果。
+
+现有的 [真实 LLM 主链路与 Next 安全专项验收记录](13_真实LLM主链路与Next安全专项验收记录.md) 是 2026-06-06 的独立主链路证据：其中记录了 `xiaomi_mimo / mimo-v2.5`、`fallback_used=false` 和 23 步主链路结果。该专项未覆盖本记录要求的所有 Provider、媒体能力、逐场景延迟和持久化产物，因此不作为本全量矩阵的结果。
+
+## 当前可核验的准备度
+
+| 项目 | 状态 | 可核验证据 | 结论边界 |
+|---|---|---|---|
+| Provider 分类和 fallback 拒绝辅助函数 | 已实现并通过单元测试 | `backend/tests/test_real_provider_acceptance_helpers.py`：3 passed | 仅证明纯函数规则；不调用 Provider 或业务 API。 |
+| 辅助模块语法 | 可编译 | `backend/.venv/bin/python -m py_compile scripts/real_provider_acceptance.py` | 不证明 CLI、网络、认证或场景执行存在。 |
+| 全量验收 CLI | 未实现 | 文件没有 `argparse`、主入口或场景执行代码 | `--preflight`、`--scenario`、`--timeout`、`--json-output` 目前均不能形成验收语义。 |
+| 真实 Provider 预检 | 未执行且当前不可由该模块执行 | 无预检输出文件或结构化记录 | 未确认文本、图像、音频、视频或沉浸课堂 Provider 配置。 |
+| 真实 Provider 全量基线 | 未执行 | 未发现 `*real*provider*.json` 或 `*provider*baseline*.json` 基线文件 | 无通过数量、失败数量、延迟、Provider/模型或产物 ID 可报告。 |
+
+## 全量状态矩阵
+
+下表列出计划中需要逐项验收的范围。所有“未执行”均表示没有可核验证据，并不表示 Provider 不可用或接口失败。
+
+| 场景 | Provider / 模型 | 状态 | API / 首次输出 / 完成耗时 | 证据 ID | 结果或失败边界 |
+|---|---|---|---|---|---|
+| Wiki 生成 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚无认证场景调用、真实响应校验和持久化页面证据。 |
+| Tutor 对话 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚无 `fallback_used=false`、引用和完成事件的全量基线。 |
+| 个性化资源生成 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚无真实响应、资源持久化和归属访问证据。 |
+| 练习生成与提交 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚无题目、提交和错题持久化基线。 |
+| 学习诊断 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚无诊断报告与建议动作的真实 Provider 证据。 |
+| 学习路径生成 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚无路径持久化和真实 Provider 证据。 |
+| 自进化分析 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚无策略、证据和风险字段的全量基线。 |
+| Agent 对话任务 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚无任务成功、`completed` 事件、助手消息和工具事件证据。 |
+| 教学图片 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚未预检图像 Provider，也无归属可访问产物。 |
+| 语音合成 / 转写 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚未预检音频 Provider，也无媒体资产证据。 |
+| 互动课件 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚无任务轮询和资源产物证据。 |
+| 课程视频 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚未预检视频 Provider，也无可访问媒体产物。 |
+| 沉浸课堂 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚无任务轮询、签名访问和导出产物证据。 |
+
+## 执行前置条件
+
+在建立真实 Provider 全量基线前，执行环境必须满足以下条件：
+
+1. 实现全量 Runner 的 CLI，并让它实际处理 `--preflight`、`--base-url`、`--timeout`、`--scenario` 和 `--json-output` 参数；未知参数或空输出不能视为成功。
+2. 使用独立测试账号和私有《数据结构》课程；测试过程不得读取其他学生数据。
+3. 后端、PostgreSQL、Redis、Worker 及需要的媒体服务均已启动，且 `base-url` 指向可认证的 `/api/v1` 服务。
+4. 每个被调用的 Provider 配置为真实 Provider；响应必须记录 Provider / 模型，并在存在该字段时要求 `fallback_used=false`。
+5. 每个媒体能力先记录“已配置”或“未配置”；未配置能力应写为 `not_configured`，不得调用其接口或记为通过。
+6. Runner 必须对每个场景保留脱敏后的请求失败边界、首个输出和完成耗时、任务/作业/产物 ID，以及归属令牌下的可访问性校验。
+
+## 复验步骤与产物位置
+
+当前已执行的准备度检查：
+
+```bash
+backend/.venv/bin/python -m pytest backend/tests/test_real_provider_acceptance_helpers.py -q
+backend/.venv/bin/python -m py_compile scripts/real_provider_acceptance.py
+```
+
+2026-07-12 的结果分别为 `3 passed` 和退出码 `0`。它们不产生 Provider 基线 JSON。
+
+在 CLI 和场景 Runner 完整实现后，才可使用以下命令建立新的基线；这些命令在本记录建立时**没有执行**：
+
+```bash
+backend/.venv/bin/python scripts/real_provider_acceptance.py \
+  --preflight \
+  --base-url http://127.0.0.1:8000/api/v1
+
+backend/.venv/bin/python scripts/real_provider_acceptance.py \
+  --base-url http://127.0.0.1:8000/api/v1 \
+  --timeout 900 \
+  --json-output /tmp/real-provider-baseline.json
+```
+
+预期产物位置为显式传入的 JSON 路径，例如 `/tmp/real-provider-baseline.json`；产物应至少包含 `provider_preflight`、逐场景结果和汇总计数。将脱敏 JSON 的路径、生成时间和每行矩阵的证据 ID 追加到本记录后，才能更新对应状态。不得用旧 JSON 代表变更后的代码状态。
+
+## 已知限制与真实性边界
+
+1. 当前辅助模块只拒绝 `mock`、`fallback`、`mock_multimodal` 和 `mock_audio` 等非真实 Provider 标识；它没有发起网络调用或检查实际配置。
+2. 当前没有真实媒体 Provider 的配置预检、延迟、作业 ID、媒体资产 ID 或可访问产物可供记录。
+3. 真实 Provider 验收会消耗外部配额并创建测试数据，必须在获得所需账号和服务权限后执行；没有这些条件时，状态应保持“未执行”或明确标为 `not_configured`。
+4. 本记录不改变现有 API、数据库、业务逻辑或测试计划；它只提供诚实的全量验收状态入口和复验规则。
diff --git a/docs/superpowers/plans/2026-07-11-real-provider-full-acceptance.md b/docs/superpowers/plans/2026-07-11-real-provider-full-acceptance.md
new file mode 100644
index 0000000..217825e
--- /dev/null
+++ b/docs/superpowers/plans/2026-07-11-real-provider-full-acceptance.md
@@ -0,0 +1,318 @@
+# Real Provider Full Acceptance Implementation Plan
+
+> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
+
+**Goal:** Produce repeatable evidence that every configured student-facing generation capability completes with a real provider, then remove only measured reliability, latency, or output-quality regressions.
+
+**Architecture:** Extend the existing `main_chain_check.py` and `agent_demo_check.py` patterns with one serial real-provider runner. The runner creates an isolated user/course, makes API requests, polls asynchronous tasks/jobs, validates provider/fallback metadata and persisted artifacts, and writes sanitized JSON plus a Markdown acceptance record. Optimizations are implemented only after a baseline record identifies the exact failing boundary.
+
+**Tech Stack:** Python 3.12, `httpx`, FastAPI `/api/v1`, PostgreSQL task/resource records, ARQ Worker, Docker Compose, pytest.
+
+## Global Constraints
+
+- Never print, persist, or commit API keys; report only whether a provider is configured.
+- A real-generation pass requires a non-Mock provider, no fallback, terminal success, and an owner-accessible persisted result.
+- Run scenarios serially; use a dedicated test account/course and bounded polling timeouts.
+- Do not change database schema, permissions, Docker topology, or user-owned learning data.
+- Reuse running Docker services; after an approved code fix restart only its affected service through `scripts/fast_deploy_code.sh`.
+- All Router, Schema, or SQLAlchemy Model edits require `python scripts/export_implementation_docs.py`; none are planned unless a verified defect requires them.
+
+---
+
+## File Structure
+
+- Create: `scripts/real_provider_acceptance.py` — serial authenticated API runner, provider preflight, scenario timing, task/job polling, assertions, sanitized JSON output.
+- Create: `backend/tests/test_real_provider_acceptance_helpers.py` — unit tests for provider classification, response assertions, timeout classification, and report sanitization without a network call.
+- Create: `docs/19_测试方案/25_真实Provider全量验收记录.md` — durable matrix containing commands, environment (without secrets), pass/fail/not-configured results, latency, artifacts, failures, and retained optimizations.
+- Modify: `docs/19_测试方案/19_测试方案.md` — add the new real-provider acceptance runner and record to the existing test entrypoint.
+- Potentially modify, only after a measured failure: the single service/provider/worker/frontend file proven to be on the failing boundary, together with its focused regression test.
+
+## Task 1: Build the deterministic real-provider acceptance runner
+
+**Files:**
+- Create: `scripts/real_provider_acceptance.py`
+- Create: `backend/tests/test_real_provider_acceptance_helpers.py`
+
+**Interfaces:**
+- Consumes: the authenticated API contracts used by `scripts/main_chain_check.py` and `scripts/agent_demo_check.py`.
+- Produces: `RealProviderAcceptance.run() -> dict[str, Any]`, JSON `{scenarios, provider_preflight, summary}` written only to an explicit output path, and nonzero exit status on any configured capability failure.
+
+- [ ] **Step 1: Write pure helper tests before adding the runner**
+
+```python
+from scripts.real_provider_acceptance import (
+    classify_provider,
+    require_real_response,
+    sanitize_error,
+)
+
+
+def test_classify_provider_rejects_mock_and_fallback() -> None:
+    assert classify_provider({"provider": "xiaomi_mimo", "fallback_used": False}) == "real"
+    assert classify_provider({"provider": "mock", "fallback_used": False}) == "mock"
+    assert classify_provider({"provider": "fallback", "fallback_used": True}) == "fallback"
+
+
+def test_require_real_response_rejects_mock_even_when_http_succeeds() -> None:
+    try:
+        require_real_response({"provider": "mock", "fallback_used": False}, "tutor")
+    except RuntimeError as exc:
+        assert "tutor" in str(exc)
+    else:
+        raise AssertionError("mock response must not pass real-provider acceptance")
+
+
+def test_sanitize_error_removes_bearer_tokens() -> None:
+    assert "secret-value" not in sanitize_error("Bearer secret-value provider failed")
+```
+
+- [ ] **Step 2: Run the helper tests and confirm they fail before implementation**
+
+Run:
+
+```bash
+docker exec zhixue-backend pytest tests/test_real_provider_acceptance_helpers.py -q
+```
+
+Expected: collection failure because `scripts.real_provider_acceptance` does not exist.
+
+- [ ] **Step 3: Implement the runner primitives and provider preflight**
+
+```python
+REAL_PROVIDER_DENYLIST = {"", "mock", "fallback", "mock_multimodal", "mock_audio"}
+
+
+def classify_provider(payload: dict[str, Any]) -> str:
+    provider = str(payload.get("provider") or "").strip().lower()
+    if payload.get("fallback_used") or provider == "fallback":
+        return "fallback"
+    return "real" if provider not in REAL_PROVIDER_DENYLIST else "mock"
+
+
+def require_real_response(payload: dict[str, Any], scenario: str) -> None:
+    state = classify_provider(payload)
+    if state != "real":
+        raise RuntimeError(f"{scenario}: expected real provider, got {state} ({payload.get('provider')!r})")
+```
+
+The runner must: create/login a unique `real_acceptance_<unix_milliseconds>` student; create one private Data Structures course; capture `perf_counter()` at request start; poll `/agent/tasks/{id}` and `/multimodal/jobs/{id}` until terminal state; verify the relevant response/resource/media URL through the owning token; and append a sanitized scenario result even if a later scenario fails.
+
+- [ ] **Step 4: Implement serial scenario coverage**
+
+Implement `run_text_scenarios()` using these existing API calls and assertions:
+
+```python
+POST /wiki/pages/generate-from-material
+POST /tutor/chat
+POST /resources/generate
+POST /quizzes/generate
+POST /quizzes/{quiz_id}/submit
+POST /diagnosis/analyze?course_id={course_id}&trigger_evolution=false
+POST /learning-paths/generate
+POST /evolution/analyze
+POST /agent/conversations/{conversation_id}/messages
+```
+
+Use `main_chain_check.py` for request-body shapes and assertions, and `agent_demo_check.py` for conversation/task polling and event persistence assertions. For each text scenario require a real `provider`, `fallback_used is False` when that field exists, expected structured fields, and persisted IDs. For the Agent scenario also require a `completed` event, `succeeded` status, an assistant message, and at least one tool event for the explicit generation prompt.
+
+Implement `run_media_scenarios()` with image, audio, courseware, video, and immersive-classroom calls only when the preflight confirms the necessary provider configuration. Validate provider/job metadata and owner-accessible media/resource output; otherwise add `not_configured` with the missing configuration name and do not call the endpoint.
+
+- [ ] **Step 5: Run helper tests and static syntax validation**
+
+Run:
+
+```bash
+docker exec zhixue-backend pytest tests/test_real_provider_acceptance_helpers.py -q
+docker exec zhixue-backend python -m py_compile /app/scripts/real_provider_acceptance.py
+```
+
+Expected: helper tests pass and compilation exits 0. If `/app/scripts` is not mounted into the running container, run the command with the project Python environment before deployment and record the exact environment limitation.
+
+- [ ] **Step 6: Commit the runner and unit tests**
+
+```bash
+git add scripts/real_provider_acceptance.py backend/tests/test_real_provider_acceptance_helpers.py
+git commit -m "test: add real provider acceptance runner"
+```
+
+## Task 2: Establish the baseline with configured real providers
+
+**Files:**
+- Modify: `docs/19_测试方案/25_真实Provider全量验收记录.md`
+- Modify: `docs/19_测试方案/19_测试方案.md`
+
+**Interfaces:**
+- Consumes: `python scripts/real_provider_acceptance.py --base-url http://127.0.0.1/api/v1 --json-output /tmp/real-provider-baseline.json`.
+- Produces: a complete Markdown matrix with each scenario’s state, provider/model, latency, artifact/task ID, and failure boundary.
+
+- [ ] **Step 1: Run configuration-only preflight**
+
+Run:
+
+```bash
+docker exec zhixue-backend python /app/scripts/real_provider_acceptance.py --preflight --base-url http://127.0.0.1/api/v1
+```
+
+Expected: text LLM configuration is reported as configured without exposing key values; each external media provider is explicitly configured or not configured.
+
+- [ ] **Step 2: Run the serial baseline suite**
+
+Run:
+
+```bash
+docker exec zhixue-backend python /app/scripts/real_provider_acceptance.py \
+  --base-url http://127.0.0.1/api/v1 \
+  --timeout 900 \
+  --json-output /tmp/real-provider-baseline.json
+```
+
+Expected: every configured scenario reaches `passed` or exits nonzero with an individual scenario record; the runner continues after a scenario failure so the result is a full matrix.
+
+- [ ] **Step 3: Write the baseline record from the sanitized JSON**
+
+Create a table with exact columns:
+
+```markdown
+| Scenario | Provider / Model | Status | API / First output / Completion | Evidence ID | Result or failure boundary |
+|---|---|---|---|---|---|
+```
+
+Classify any failure as `request/auth`, `provider`, `structured-output`, `queue/worker`, `persistence`, `artifact`, or `frontend`, and include the reproducible command.
+
+- [ ] **Step 4: Link the runner and record from the test-index document**
+
+Add under “真实LLM专项”:
+
+```markdown
+真实 Provider 全量验收使用 `python scripts/real_provider_acceptance.py`。它只接受真实 Provider、无 fallback 且可访问的持久化结果；最新证据见 `25_真实Provider全量验收记录.md`。
+```
+
+- [ ] **Step 5: Validate documentation and commit the baseline record**
+
+Run:
+
+```bash
+python scripts/check_docs.py
+git diff --check
+```
+
+Expected: both commands exit 0.
+
+```bash
+git add docs/19_测试方案/19_测试方案.md docs/19_测试方案/25_真实Provider全量验收记录.md
+git commit -m "docs: record real provider acceptance baseline"
+```
+
+## Task 3: Repair and measure one verified bottleneck at a time
+
+**Files:**
+- Modify: one file at the proven boundary, selected only after Task 2.
+- Modify: the corresponding existing test file under `backend/tests/`.
+- Modify: `docs/19_测试方案/25_真实Provider全量验收记录.md`.
+
+**Interfaces:**
+- Consumes: a failed or slow scenario row from Task 2 and its sanitized task/provider/error evidence.
+- Produces: one focused regression test and before/after measurement for the same scenario.
+
+- [ ] **Step 1: Select exactly one root-cause hypothesis from the baseline**
+
+Write the hypothesis in the acceptance record before editing, for example:
+
+```markdown
+Hypothesis: `GroundedQAPipeline` blocks the SSE `done` event on a non-critical structured memory reflection; moving that reflection to its existing post-response event path reduces completion latency without changing the cited answer.
+```
+
+Do not combine prompt, queue, timeout, and UI changes in the same iteration.
+
+- [ ] **Step 2: Add a focused failing regression test**
+
+For an SSE completion blocker, use an existing Tutor pipeline test and assert the critical response finishes even if the non-critical post-processing task fails:
+
+```python
+async def test_streaming_answer_completes_when_post_response_reflection_fails(
+    pipeline: GroundedQAPipeline,
+    payload: TutorChatRequest,
+    user: User,
+) -> None:
+    pipeline._schedule_post_response = AsyncMock(side_effect=RuntimeError("reflection unavailable"))
+    events = [event async for event in pipeline.stream_chat(payload, user)]
+    assert any(event["event"] == "done" for event in events)
+```
+
+For a structured-provider failure, assert the provider retry formatter yields valid schema JSON from the captured malformed shape. For a Worker failure, assert a queued task transitions to `failed` with a correlated error rather than remaining `running`.
+
+- [ ] **Step 3: Run only the new regression test and confirm it fails**
+
+Run the exact relevant pytest node, for example:
+
+```bash
+docker exec zhixue-backend pytest tests/test_tutor.py::test_streaming_answer_completes_when_post_response_reflection_fails -q
+```
+
+Expected: fail for the observed baseline behavior, not for unrelated environment setup.
+
+- [ ] **Step 4: Implement the smallest boundary fix and deploy only its service**
+
+Make one focused change, run the exact test to passing, then use one of:
+
+```bash
+./scripts/fast_deploy_code.sh backend
+./scripts/fast_deploy_code.sh frontend
+```
+
+Expected: only the service containing the fix is refreshed; database, Redis, and OpenMAIC remain running.
+
+- [ ] **Step 5: Re-run the same acceptance scenario and compare results**
+
+Run:
+
+```bash
+docker exec zhixue-backend python /app/scripts/real_provider_acceptance.py \
+  --scenario tutor_fast \
+  --base-url http://127.0.0.1/api/v1 \
+  --json-output /tmp/real-provider-after.json
+```
+
+Expected: status changes to `passed`, or the measured completion time improves while output/provider/citations/artifact checks remain unchanged.
+
+- [ ] **Step 6: Record the retained change and run relevant checks**
+
+Run the exact focused pytest command, the scenario rerun, `git diff --check`, and—if frontend code changed—`npm run typecheck && npm run build` in the frontend environment. Append before/after timings and remaining external-provider limitations to the acceptance record, then commit the code, test, and record together.
+
+## Task 4: Final full rerun and handoff
+
+**Files:**
+- Modify: `docs/19_测试方案/25_真实Provider全量验收记录.md`
+
+**Interfaces:**
+- Consumes: the completed runner and any Task 3 fixes.
+- Produces: the final all-scenario result matrix and a clear list of not-configured or provider-limited capabilities.
+
+- [ ] **Step 1: Run the full serial suite again**
+
+Run the same command as Task 2 Step 2 with a fresh JSON output path. Do not reuse baseline artifacts as evidence of the final code state.
+
+- [ ] **Step 2: Verify operational state**
+
+Run:
+
+```bash
+docker compose -f docker-compose.prod.yml ps
+curl -fsS http://127.0.0.1/health
+git diff --check
+```
+
+Expected: required services are running, health returns `{"status":"ok","service":"zhixue-workshop"}`, and the worktree has no whitespace error.
+
+- [ ] **Step 3: Complete the final acceptance record**
+
+The conclusion must enumerate: pass count, fail count, not-configured count, real providers/models, retained optimizations with before/after data, and remaining risk. Do not describe a Mock/fallback response or unavailable provider as a pass.
+
+- [ ] **Step 4: Commit and hand off**
+
+```bash
+git add docs/19_测试方案/25_真实Provider全量验收记录.md
+git commit -m "docs: finalize real provider acceptance results"
+```
+
+Report the final matrix, exact verification commands, affected files, database/API changes (normally none), and any provider-account limitation that requires user action.
diff --git "a/docs/\345\275\223\345\211\215\345\256\236\347\216\260\345\237\272\347\272\277.md" "b/docs/\345\275\223\345\211\215\345\256\236\347\216\260\345\237\272\347\272\277.md"
index 3545130..0dcf0f3 100644
--- "a/docs/\345\275\223\345\211\215\345\256\236\347\216\260\345\237\272\347\272\277.md"
+++ "b/docs/\345\275\223\345\211\215\345\256\236\347\216\260\345\237\272\347\272\277.md"
@@ -19,21 +19,21 @@
 | FastAPI HTTP 操作 | 147 |
 | SQLAlchemy ORM 表 | 44 |
 | Alembic migration | 19+ |
 | Agent 类 | 15（含 IntentRouter、Orchestrator、KnowledgeGraph 与 Review） |
 | Agent Tool Registry | 24 个工具 |
 | API 路由模块 | 27 |
 | Service 文件 | 65 |
 | 后端测试文件 | 54 |
 | Next.js 页面路由 | 11 |
 | Stitch HTML 页面 | 8 |
-| 后端 pytest | 442 passed |
+| 后端 pytest | 466 passed |
 | 真实 LLM 主链路 | 23 步通过 |
 | 前端依赖审计 | 0 vulnerabilities |
 
 ## 当前前端形态
 
 | 路由 | 实际承载 |
 |---|---|
 | `/` | React `LandingPage`，品牌首页与登录/注册弹窗 |
 | `/home` | `home.html`，登录后学习首页 |
 | `/courses` | `courses.html`，课程创建、编辑、归档入口 |
@@ -58,20 +58,21 @@
 - Phase 2/3 固定任务执行器保留为 `legacy_workflow` 回滚链路；Phase 3.1 已新增 LangGraph 1.x 动态学习智能体，使用 MiMo Supervisor 根据目标和观察动态选择工具、继续执行或重新规划。正式验收见 `docs/19_测试方案/16_Phase3.1LangGraph真正智能体阶段验收记录.md`。
 - **Supervisor 决策模型（2026-06-08）**：LLM 主导 native function calling；规则层 `_apply_safety_net` 仅在必交付物缺失（语音/视频/练习等）、显式「基于资料/引用」约束、用户 `tool_hints` 或 Mock 空转 fallback 时介入；待交付物列表在工具约束过滤之后计算，避免安全网与 deliverable 对齐顺序不一致。Mock Provider 在有 tools 时会模拟 native `tool_calls`。
 - Phase 3.1 真实 MiMo 20 条场景评测已通过：场景通过率 100%、任务完成率 95%、工具选择准确率 100%、重规划成功率 100%、高风险拦截率 100%。
 - Phase 3.1 已补稳定演示脚本：`scripts/start_phase31_demo.ps1` 启动 backend / arq Worker / frontend，`scripts/agent_demo_check.py` 通过真实 HTTP API 验证统一 Agent 入口、工具事件、对话消息和画像证据。
 - `/assistant` 会按课程恢复已有 Agent 会话，回放用户消息、规划/工具/观察/Review/多模态进度等可展开流式步骤、完整事件日志和 Assistant 最终回答；切换或新建会话时会停止当前页面 SSE 监听，后台 Agent 任务可继续运行，用户可手动恢复查看或取消任务。
 - `/assistant` 的简单寒暄使用轻量直答路径：快速模式不构建 RAG/画像上下文，智能体模式不进入 Review、长期记忆反思和对话知识抽取；普通快速问答关闭模型 thinking 并在流式结束后使用规则校验，避免第二次同步 Review LLM 阻塞完成状态。
 - `/assistant` 的资料问答已统一到 `GroundedQAPipeline`：文档与 Wiki 证据保留真实来源 ID，以 `[S1]` 形式生成和校验引用；主回答只调用一次 LLM，反馈所需学习记录同步落库，画像/记忆等非关键处理异步执行。Agent 的纯资料问答直接复用同一结果，避免再次检索和再次生成；需要多模态产物时先检索课程依据再生成产物。
 - Tutor SSE 前端只在首个回答增量前允许一次非流式降级，支持 AbortSignal、无 `done` 结束检测和请求所有权隔离，避免重复回答、幽灵停止状态与旧请求覆盖新会话。课程切换会停止活动流并清理课程相关状态。
 - 登录后的学生端页面已挂载全站“知知”桌宠：支持拖拽吸附、跨 Stitch iframe 常驻、任务完成气泡、提醒收件箱、刷题/路径催学及提醒偏好设置；公开首页与认证页面不显示。
 - Agent 运行时将长期记忆反思视为非关键后置步骤：反思失败会记录降级事件但不阻断最终回答；arq Worker 启动时会把长时间无进展的 `running` LangGraph 任务标记为失败，避免历史任务永久卡住。
+- **Agent Runtime 收敛（2026-07-12）**：Supervisor 对可识别意图仅提供对应的候选工具（无候选时保留全量回退）；事件与动态步骤继续记录既有的执行时序和耗时；Worker 以条件更新原子认领 `queued` 任务。此次收敛未新增数据库表或 API。
 - Phase 4 对话式画像 v1 已接入：Supervisor 可将“专业、年级、学习目标、学习偏好、薄弱点、错误模式”等自然语言信息路由到 `update_profile_from_dialogue` 工具，由 `ProfileService` 写入 `student_profiles.strategy_summary.dialogue_profile` 和 `learning_preferences.prompt_params`，并在 `/path-profile` 展示证据。
 - 个性化学习闭环已完成第一版工程化修复：长期记忆使用稳定 `memory_key` 合并强化、反思水位仅处理新行为；`MemoryAgent` 按 `params.course_id` 解析课程作用域（不再误用 `context.course_id`）；课程作用域最多保留 20 条活跃记忆、全局最多 10 条，超限与历史重复记录只归档不删除；Tutor、Resource 与个性化上下文只加载当前课程最相关的 5 条活跃记忆。
 - 学生画像已拆分为全局 `student_profiles` 与课程级 `student_course_profiles`。非寒暄问答完成后通过 EventBus 后置提取画像信号，使用消息 ID 幂等；掌握度写入课程画像，不再覆盖其他课程快照。
 - 自进化策略应用已从“仅修改 active 状态”升级为物化执行：`qa_style` / `resource_strategy` 写入学习偏好与 Prompt 参数，`difficulty` / `recommendation` / `learning_path` 写入课程策略上下文；推荐与路径绑定策略版本，回滚恢复上一版实际参数，低风险策略审核后自动生效。
 - 首页学习分析已接入真实 `learning_sessions` 与汇总 API；`/assistant`、`/knowledge`、`/practice` 仅在页面可见且最近有交互时发送心跳，服务端单次最多累计 60 秒。首页本周/本月时长、掌握度和每日柱状图不再使用 `18.5 小时 / 82%` 静态值。
 - RAG 检索已从单纯向量检索增强为向量检索 + 关键词检索 + metadata 过滤 + 轻量 rerank/source diversity 的 HybridRetriever。
 - 资料知识点抽取已升级为“规则候选召回 → LLM 结构化归一化 → 确定性校验 / 规则降级”：单份资料最多保留 30 个有来源的细粒度知识点，整理元数据记录 aliases、source chunk/material、置信度与降级原因；Wiki 生成仅处理当前资料绑定的知识点，避免跨资料页面混入，`/knowledge` 展示候选、合并、拒绝、保留和整理方式统计。
 - Redis 已用于 arq 持久后台任务队列和实时 Agent 事件通知；当前本机 Redis 3.0 不支持 Stream，运行时自动兼容为 PostgreSQL 追加事件 + Redis Pub/Sub。
 - Agent 画像上下文使用 Redis 30 分钟智能缓存；画像编辑、对话画像更新、画像重建和掌握度快照同步后立即失效，Redis 不可用时回退数据库。
 - 上传文件使用本地存储 `backend/storage`；当前无 MinIO Adapter。
diff --git a/scripts/fast_deploy_code.sh b/scripts/fast_deploy_code.sh
index c6d150a..86119a1 100755
--- a/scripts/fast_deploy_code.sh
+++ b/scripts/fast_deploy_code.sh
@@ -11,20 +11,22 @@ COMPOSE_FILE="${ROOT}/docker-compose.prod.yml"
 TARGET="${1:-all}"
 
 log() { echo "[fast-deploy] $*"; }
 
 sync_backend() {
   log "同步 backend/app → zhixue-backend / zhixue-worker"
   docker cp "${ROOT}/backend/app/." zhixue-backend:/app/app/
   docker cp "${ROOT}/backend/app/." zhixue-worker:/app/app/
   log "重启 backend worker"
   docker compose -f "${COMPOSE_FILE}" restart backend worker
+  log "重启 nginx，刷新 backend 上游地址"
+  docker compose -f "${COMPOSE_FILE}" restart nginx 2>/dev/null || true
   log "检查 worker 关键依赖 moviepy"
   docker exec zhixue-worker python -c "import moviepy" 2>/dev/null \
     || docker exec zhixue-worker pip install -q 'moviepy>=2.0.0'
 }
 
 build_frontend_app_layer() {
   log "同步 stitch-pages → frontend 容器 public 目录"
   docker cp "${ROOT}/frontend/public/stitch-pages/." zhixue-frontend:/app/public/stitch-pages/ 2>/dev/null || true
   log "仅重建 frontend 应用层（deps 层走 Docker 缓存，不装 torch）"
   docker compose -f "${COMPOSE_FILE}" build frontend
diff --git a/scripts/real_provider_acceptance.py b/scripts/real_provider_acceptance.py
new file mode 100644
index 0000000..52da5b2
--- /dev/null
+++ b/scripts/real_provider_acceptance.py
@@ -0,0 +1,26 @@
+from __future__ import annotations
+
+import re
+from typing import Any
+
+
+REAL_PROVIDER_DENYLIST = {"", "mock", "fallback", "mock_multimodal", "mock_audio"}
+
+
+def classify_provider(payload: dict[str, Any]) -> str:
+    provider = str(payload.get("provider") or "").strip().lower()
+    if payload.get("fallback_used") or provider == "fallback":
+        return "fallback"
+    return "real" if provider not in REAL_PROVIDER_DENYLIST else "mock"
+
+
+def require_real_response(payload: dict[str, Any], scenario: str) -> None:
+    state = classify_provider(payload)
+    if state != "real":
+        raise RuntimeError(
+            f"{scenario}: expected real provider, got {state} ({payload.get('provider')!r})"
+        )
+
+
+def sanitize_error(value: str) -> str:
+    return re.sub(r"(?i)(bearer\s+)[^\s,;]+", r"\1[REDACTED]", value)
