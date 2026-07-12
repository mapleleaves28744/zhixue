from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.tools import ToolContext, ToolExecutionResult, ToolRegistry
from app.agent_runtime.toolsets.common import register_tool
from app.models.user import User


def register_media_tools(
    registry: ToolRegistry,
    db: AsyncSession,
    current_user: User,
    *,
    tool_names: Iterable[str] | None = None,
) -> None:
    selected = set(tool_names or ())

    def include(name: str) -> bool:
        return not selected or name in selected

    async def transcribe_audio_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.llm.audio_provider import _safe_audio_byte_count, build_audio_provider

        audio_base64 = str(arguments["audio_base64"])
        byte_count = _safe_audio_byte_count(audio_base64)
        result = await build_audio_provider().transcribe(
            audio_base64,
            filename=str(arguments.get("filename") or "audio.wav"),
            language=str(arguments.get("language") or "zh"),
        )
        raw = result.raw or {}
        return ToolExecutionResult(
            output={
                "text": result.text,
                "duration_ms": result.duration_ms,
                "language": result.language,
                "provider": result.provider,
                "model": result.model,
                "audio_bytes": byte_count,
                "fallback_used": bool(raw.get("fallback_used")),
                "failed_provider": raw.get("failed_provider"),
                "fallback_reason": raw.get("fallback_reason"),
            },
            evidence=[f"语音识别完成，provider={result.provider}，模型={result.model}", f"输入音频 {byte_count} bytes，识别文本 {len(result.text)} 字"],
        )

    async def synthesize_speech_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        import base64

        from app.llm.audio_provider import MIMO_TTS_MODEL, MIMO_TTS_VOICECLONE_MODEL, MIMO_TTS_VOICEDESIGN_MODEL, build_audio_provider
        from app.repositories.media_repository import MediaRepository
        from app.services.media_storage_service import MediaStorageService

        text = str(arguments["text"]).strip()
        model_type = str(arguments.get("model_type") or "tts")
        model_map = {"tts": MIMO_TTS_MODEL, "voiceclone": MIMO_TTS_VOICECLONE_MODEL, "voicedesign": MIMO_TTS_VOICEDESIGN_MODEL}
        result = await build_audio_provider().synthesize(
            text,
            voice=str(arguments.get("voice") or "") or None,
            speed=float(arguments.get("speed") or 1.0),
            response_format=str(arguments.get("response_format") or "wav"),
            model=model_map.get(model_type, MIMO_TTS_MODEL),
        )
        raw = result.raw or {}
        audio_format = result.format or "wav"
        padding = "=" * (-len(result.audio_base64) % 4)
        audio_bytes = base64.b64decode(result.audio_base64 + padding)
        storage_path, file_size, mime_type = MediaStorageService().save_bytes(data=audio_bytes, asset_type="audio", suffix=f".{audio_format}")
        topic = text[:30].replace("\n", " ")
        asset = await MediaRepository(db).create_asset(
            user_id=current_user.id,
            course_id=context.course_id,
            asset_type="audio",
            title=f"语音讲解 · {topic}",
            storage_path=storage_path,
            mime_type=mime_type,
            file_size=file_size,
            duration_ms=result.duration_ms,
            agent_task_id=context.task_id,
            tool_call_id=context.tool_call_id,
            provider=result.provider,
            model_name=result.model,
            prompt=text[:2000],
        )
        return ToolExecutionResult(
            output={
                "asset_id": str(asset.id),
                "audio_base64": result.audio_base64,
                "format": audio_format,
                "model": result.model,
                "provider": result.provider,
                "duration_ms": result.duration_ms,
                "text_length": len(text),
                "fallback_used": bool(raw.get("fallback_used")),
                "failed_provider": raw.get("failed_provider"),
                "fallback_reason": raw.get("fallback_reason"),
            },
            evidence=[f"语音合成完成，provider={result.provider}，模型={result.model}", f"输出格式 {audio_format}，文本 {len(text)} 字"],
            artifact_refs=[{"type": "audio", "asset_id": str(asset.id), "title": asset.title, "mime_type": mime_type}],
        )

    async def generate_educational_image_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.services.multimodal_resource_service import MultimodalResourceService

        result = await MultimodalResourceService(db).generate_image(
            current_user=current_user,
            course_id=context.course_id,
            topic=str(arguments["topic"]),
            image_type=str(arguments.get("image_type") or "concept_illustration"),
            style=str(arguments.get("style") or "clean educational illustration"),
            size=str(arguments.get("size") or "1280x720"),
            requirement=str(arguments.get("requirement") or "") or None,
            tool_context=context,
        )
        mode = str(result.get("generation_mode") or "image")
        if mode.startswith("mermaid"):
            subtype = str(result.get("subtype") or "mindmap")
            return ToolExecutionResult(output=result, evidence=result.get("citations") or [], citations=result.get("citations") or [], artifact_refs=[{"type": "resource", "subtype": subtype, "id": result["resource_id"], "title": result.get("title")}])
        return ToolExecutionResult(output=result, evidence=result.get("citations") or [], citations=result.get("citations") or [], artifact_refs=[{"type": "media_asset", "subtype": "image", **result}])

    async def generate_lesson_video_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.services.multimodal_resource_service import MultimodalResourceService

        result = await MultimodalResourceService(db).create_video_job(
            current_user=current_user,
            course_id=context.course_id,
            topic=str(arguments["topic"]),
            duration_seconds=int(arguments.get("duration_seconds") or 90),
            visual_mode=str(arguments.get("visual_mode") or "storyboard"),
            voice=str(arguments.get("voice") or "") or None,
            target_level=str(arguments.get("target_level") or "") or None,
            tool_context=context,
        )
        return ToolExecutionResult(output=result, evidence=["视频生成任务已创建，后台会持续写入进度事件。"], artifact_refs=[{"type": "media_job", "subtype": "video", **result}])

    async def generate_immersive_classroom_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.services.immersive_classroom_service import ImmersiveClassroomService

        result = await ImmersiveClassroomService(db).create_job(
            current_user=current_user,
            course_id=context.course_id,
            topic=str(arguments["topic"]),
            learning_goal=str(arguments.get("learning_goal") or "") or None,
            generate_video_export=bool(arguments.get("generate_video_export", True)),
            enable_images=bool(arguments.get("enable_images", True)),
            enable_video_clips=bool(arguments.get("enable_video_clips", False)),
            enable_tts=bool(arguments.get("enable_tts", True)),
            tool_context=context,
        )
        return ToolExecutionResult(output=result, evidence=["已创建基于课程 RAG 与学生画像的沉浸课堂任务，后台将继续生成课堂和配音字幕 MP4。"], artifact_refs=[{"type": "media_job", "subtype": "immersive_classroom", **result}])

    async def generate_storyboard_html_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.services.multimodal_resource_service import MultimodalResourceService

        result = await MultimodalResourceService(db).generate_storyboard_html(
            current_user=current_user,
            course_id=context.course_id,
            topic=str(arguments["topic"]),
            duration_seconds=int(arguments.get("duration_seconds") or 90),
            requirement=str(arguments.get("requirement") or "") or None,
            tool_context=context,
        )
        return ToolExecutionResult(output=result, evidence=result.get("citations") or [], citations=result.get("citations") or [], artifact_refs=[{"type": "media_asset", "subtype": "storyboard", **result}])

    async def generate_interactive_courseware_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.services.multimodal_resource_service import MultimodalResourceService

        result = await MultimodalResourceService(db).generate_courseware(
            current_user=current_user,
            course_id=context.course_id,
            topic=str(arguments["topic"]),
            interaction_type=str(arguments.get("interaction_type") or "stepper"),
            target_level=str(arguments.get("target_level") or "") or None,
            requirement=str(arguments.get("requirement") or "") or None,
            tool_context=context,
        )
        return ToolExecutionResult(output=result, evidence=result.get("citations") or [], citations=result.get("citations") or [], artifact_refs=[{"type": "media_asset", "subtype": "courseware", **result}])

    if include("transcribe_audio"):
        register_tool(registry, "transcribe_audio", "将音频文件转换为文字，支持语音提问、语音笔记等场景。", "TutorAgent", {"audio_base64": {"type": "string", "description": "Base64 编码的音频数据"}, "filename": {"type": "string", "description": "文件名（用于推断格式）"}, "language": {"type": "string", "description": "语言代码，默认 zh"}}, ["audio_base64"], transcribe_audio_handler, timeout_seconds=60)
    if include("synthesize_speech"):
        register_tool(registry, "synthesize_speech", "将文字转换为语音，用于讲解朗读、错题语音反馈等场景。", "TutorAgent", {"text": {"type": "string", "description": "要转换的文字"}, "model_type": {"type": "string", "enum": ["tts", "voiceclone", "voicedesign"]}, "voice": {"type": "string", "description": "音色，可由具体 Provider 解释"}, "speed": {"type": "number", "minimum": 0.5, "maximum": 2.0}, "response_format": {"type": "string", "enum": ["wav", "mp3"]}}, ["text"], synthesize_speech_handler, timeout_seconds=120)
    if include("generate_educational_image"):
        register_tool(registry, "generate_educational_image", "基于课程资料、学生画像和知识主题生成教学插图、概念图、类比图或封面图。", "VisualResourceAgent", {"topic": {"type": "string", "minLength": 1}, "image_type": {"type": "string", "enum": ["concept_illustration", "process_visual", "analogy", "cover", "summary_card"]}, "style": {"type": "string"}, "size": {"type": "string", "enum": ["1024x1024", "1280x720", "720x1280", "1024x768"]}, "requirement": {"type": "string"}}, ["topic"], generate_educational_image_handler, writes_db=True, timeout_seconds=180)
    if include("generate_immersive_classroom"):
        register_tool(registry, "generate_immersive_classroom", "基于课程资料、学生画像与薄弱点，一键生成 OpenMAIC 沉浸课堂，并可导出配音字幕知识点讲解 MP4。", "ImmersiveClassroomAgent", {"topic": {"type": "string", "minLength": 1}, "learning_goal": {"type": "string"}, "generate_video_export": {"type": "boolean"}, "enable_images": {"type": "boolean"}, "enable_video_clips": {"type": "boolean"}, "enable_tts": {"type": "boolean"}}, ["topic"], generate_immersive_classroom_handler, writes_db=True, timeout_seconds=30)
    if include("generate_lesson_video"):
        register_tool(registry, "generate_lesson_video", "创建短讲解视频（MP4）生成任务。仅当用户明确要「视频/短视频/动画讲解」时使用；PPT/幻灯片/课件应使用 generate_interactive_courseware。", "VideoResourceAgent", {"topic": {"type": "string", "minLength": 1}, "duration_seconds": {"type": "integer", "minimum": 30, "maximum": 240}, "visual_mode": {"type": "string", "enum": ["storyboard", "animated_diagram", "t2v_broll", "mixed"]}, "voice": {"type": "string"}, "target_level": {"type": "string"}}, ["topic"], generate_lesson_video_handler, writes_db=True, timeout_seconds=30)
    if include("generate_storyboard_html"):
        register_tool(registry, "generate_storyboard_html", "基于课程资料生成分镜 HTML 讲解页，可在 sandbox iframe 中预览（文生视频演示替代）。", "VideoResourceAgent", {"topic": {"type": "string", "minLength": 1}, "duration_seconds": {"type": "integer", "minimum": 30, "maximum": 240}, "requirement": {"type": "string"}}, ["topic"], generate_storyboard_html_handler, writes_db=True, timeout_seconds=120)
    if include("generate_interactive_courseware"):
        register_tool(registry, "generate_interactive_courseware", "基于 html-ppt-skill 生成多页 HTML 互动课件（PPT/幻灯片/slides/deck）。用户要 ppt、课件、幻灯片、翻页演示时用此工具，不是讲解视频。", "CoursewareAgent", {"topic": {"type": "string", "minLength": 1}, "interaction_type": {"type": "string", "enum": ["stepper", "drag_sort", "quiz_simulation", "graph_traversal", "timeline"]}, "target_level": {"type": "string"}, "requirement": {"type": "string"}}, ["topic"], generate_interactive_courseware_handler, writes_db=True, timeout_seconds=180)
