# Review package: 426a39a33bf17afeb3b972ec2487e847d985bbea..HEAD

## Commits
5b8a280 refactor: split agent service toolsets

## Files changed
 backend/app/agent_runtime/service_tools.py         | 900 +--------------------
 backend/app/agent_runtime/toolsets/__init__.py     |  13 +
 backend/app/agent_runtime/toolsets/common.py       |  39 +
 .../app/agent_runtime/toolsets/knowledge_tools.py  | 139 ++++
 .../app/agent_runtime/toolsets/learning_tools.py   | 154 ++++
 backend/app/agent_runtime/toolsets/media_tools.py  | 196 +++++
 .../app/agent_runtime/toolsets/profile_tools.py    |  91 +++
 backend/app/agent_runtime/toolsets/review_tools.py |  53 ++
 backend/tests/test_agent_runtime.py                |  61 +-
 9 files changed, 771 insertions(+), 875 deletions(-)

## Diff
diff --git a/backend/app/agent_runtime/service_tools.py b/backend/app/agent_runtime/service_tools.py
index 5b683a8..304b3ad 100644
--- a/backend/app/agent_runtime/service_tools.py
+++ b/backend/app/agent_runtime/service_tools.py
@@ -1,891 +1,43 @@
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
     registry = ToolRegistry(result_loader=result_loader, result_saver=result_saver)
 
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
-    )
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
+    _register_toolsets(registry, db, current_user)
     return registry
-
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
diff --git a/backend/tests/test_agent_runtime.py b/backend/tests/test_agent_runtime.py
index c7bcb9a..217d3a6 100644
--- a/backend/tests/test_agent_runtime.py
+++ b/backend/tests/test_agent_runtime.py
@@ -28,20 +28,79 @@ class QueryInput(SimpleNamespace):
     pass
 
 
 def schema(name: str) -> dict[str, object]:
     return {
         "type": "function",
         "function": {"name": name, "parameters": {"type": "object"}},
     }
 
 
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
+    schemas = {
+        item["function"]["name"]: item["function"]["parameters"]
+        for item in registry.tool_schemas()
+    }
+
+    assert set(schemas) == EXPECTED_LEARNING_TOOL_NAMES
+    assert schemas["generate_interactive_courseware"]["required"] == ["topic"]
+    assert registry.risk_level("apply_evolution_strategy") == "high"
+    assert registry.requires_confirmation("apply_evolution_strategy") is True
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
 def test_course_qa_exposes_only_grounded_tools() -> None:
     tools = [
         schema(name)
         for name in ("search_course_knowledge", "answer_course_question", "generate_quiz")
     ]
 
     selected = select_tool_schemas(
         {"goal": "解释栈", "tool_hints": [], "skip_tools": []}, tools
     )
 
@@ -1133,21 +1192,21 @@ def test_default_learning_tool_registry_exposes_specialized_agents_and_risk_boun
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
