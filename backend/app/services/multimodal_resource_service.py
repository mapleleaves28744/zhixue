from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from arq.connections import RedisSettings, create_pool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.tools import ToolContext
from app.core.config import settings
from app.llm.multimodal_provider import build_multimodal_provider
from app.models.user import User
from app.repositories.media_repository import MediaRepository
from app.repositories.resource_repository import ResourceRepository
from app.services.course_service import CourseService
from app.services.courseware_service import CoursewareService
from app.services.media_storage_service import MediaStorageService
from app.services.multimodal_brief_service import MultimodalBriefService
from app.services.video_render_service import VideoRenderService, build_storyboard


class MultimodalResourceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.media = MediaRepository(db)
        self.resources = ResourceRepository(db)
        self.storage = MediaStorageService()
        self.provider = build_multimodal_provider()

    async def generate_image(
        self,
        *,
        current_user: User,
        course_id: UUID,
        topic: str,
        image_type: str = "concept_illustration",
        style: str | None = None,
        size: str = "1280x720",
        requirement: str | None = None,
        tool_context: ToolContext | None = None,
    ) -> dict[str, Any]:
        await CourseService(self.db).get_readable_course(course_id, current_user)
        brief = await MultimodalBriefService(self.db).build_brief(
            current_user=current_user,
            course_id=course_id,
            topic=topic,
            modality="image",
            requirement=requirement,
        )
        prompt = self._image_prompt(topic, image_type, style, requirement, brief)
        result = await self.provider.generate_image(prompt=prompt, size=size, style=style)
        suffix = ".png" if result.mime_type == "image/png" else ".jpg"
        path, file_size, mime = self.storage.save_bytes(data=result.image_bytes, asset_type="image", suffix=suffix)
        resource = await self.resources.create(
            user_id=current_user.id,
            course_id=course_id,
            knowledge_id=None,
            wiki_page_id=None,
            resource_type="image",
            title=f"{topic} 教学插图",
            content=f"已生成《{topic}》教学插图。生成依据包含 {len(brief['citations'])} 条课程引用。",
            citations=brief["citations"],
            personalized_reason=brief.get("style_hint"),
            model_name=result.model,
            prompt_version_id=None,
        )
        asset = await self.media.create_asset(
            user_id=current_user.id,
            course_id=course_id,
            resource_id=resource.id,
            agent_task_id=tool_context.task_id if tool_context else None,
            conversation_id=tool_context.conversation_id if tool_context else None,
            tool_call_id=tool_context.tool_call_id if tool_context else None,
            asset_type="image",
            title=resource.title,
            description=resource.content,
            storage_path=path,
            mime_type=mime,
            file_size=file_size,
            provider=result.provider,
            model_name=result.model,
            prompt=prompt,
            citations=brief["citations"],
            safety_result={"passed": True, "risk_level": "low", "mode": "image_brief_based"},
            render_meta={"image_type": image_type, "size": size, "raw": result.raw},
        )
        await self.db.commit()
        return self._asset_response(asset, resource_id=resource.id)

    async def generate_storyboard_html(
        self,
        *,
        current_user: User,
        course_id: UUID,
        topic: str,
        duration_seconds: int = 90,
        requirement: str | None = None,
        tool_context: ToolContext | None = None,
    ) -> dict[str, Any]:
        await CourseService(self.db).get_readable_course(course_id, current_user)
        brief = await MultimodalBriefService(self.db).build_brief(
            current_user=current_user,
            course_id=course_id,
            topic=topic,
            modality="storyboard_html",
            requirement=requirement,
        )
        storyboard = build_storyboard(topic, brief, duration_seconds)
        renderer = VideoRenderService()
        html_content = renderer.render_storyboard_html(topic, storyboard)
        path, file_size, mime = self.storage.save_text(text=html_content, asset_type="storyboard", suffix=".html")
        resource = await self.resources.create(
            user_id=current_user.id,
            course_id=course_id,
            knowledge_id=None,
            wiki_page_id=None,
            resource_type="video",
            title=f"{topic} 讲解分镜",
            content="已生成分镜 HTML，可在 sandbox iframe 中预览。",
            citations=brief["citations"],
            personalized_reason=brief.get("style_hint"),
            model_name="storyboard-template-v1",
            prompt_version_id=None,
        )
        asset = await self.media.create_asset(
            user_id=current_user.id,
            course_id=course_id,
            resource_id=resource.id,
            agent_task_id=tool_context.task_id if tool_context else None,
            conversation_id=tool_context.conversation_id if tool_context else None,
            tool_call_id=tool_context.tool_call_id if tool_context else None,
            asset_type="html",
            title=resource.title,
            description=resource.content,
            storage_path=path,
            mime_type=mime,
            file_size=file_size,
            provider="storyboard_template",
            model_name="storyboard-template-v1",
            citations=brief["citations"],
            safety_result={"passed": True, "risk_level": "low", "mode": "storyboard_html"},
            render_meta={"storyboard": storyboard, "duration_seconds": duration_seconds},
        )
        await self.db.commit()
        return self._asset_response(asset, resource_id=resource.id, extra={"subtype": "storyboard"})

    async def create_video_job(
        self,
        *,
        current_user: User,
        course_id: UUID,
        topic: str,
        duration_seconds: int = 90,
        visual_mode: str = "storyboard",
        voice: str | None = None,
        target_level: str | None = None,
        tool_context: ToolContext | None = None,
    ) -> dict[str, Any]:
        await CourseService(self.db).get_readable_course(course_id, current_user)
        brief = await MultimodalBriefService(self.db).build_brief(
            current_user=current_user,
            course_id=course_id,
            topic=topic,
            modality="video",
            requirement=target_level,
        )
        resource = await self.resources.create(
            user_id=current_user.id,
            course_id=course_id,
            knowledge_id=None,
            wiki_page_id=None,
            resource_type="video",
            title=f"{topic} 个性化讲解视频",
            content="视频任务已创建，正在生成脚本、分镜和视频文件。",
            citations=brief["citations"],
            personalized_reason=brief.get("style_hint"),
            model_name=self.provider.provider_name,
            prompt_version_id=None,
        )
        payload = {
            "topic": topic,
            "duration_seconds": duration_seconds,
            "visual_mode": visual_mode,
            "voice": voice,
            "target_level": target_level,
            "brief": brief,
        }
        idem = (
            tool_context.idempotency_key
            if tool_context
            else f"video:{current_user.id}:{course_id}:{hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))}"
        )
        job = await self.media.create_job(
            user_id=current_user.id,
            course_id=course_id,
            resource_id=resource.id,
            job_type="video",
            idempotency_key=idem,
            provider=self.provider.provider_name,
            input_payload=payload,
            agent_task_id=tool_context.task_id if tool_context else None,
            conversation_id=tool_context.conversation_id if tool_context else None,
            tool_call_id=tool_context.tool_call_id if tool_context else None,
        )
        await self.db.commit()
        await self.enqueue_video_job(job.id)
        return {
            "job_id": str(job.id),
            "resource_id": str(resource.id),
            "status": job.status,
            "stage": job.stage,
            "progress": job.progress,
            "message": "视频任务已进入后台队列，可在 Agent 时间线查看进度。",
        }

    async def generate_courseware(
        self,
        *,
        current_user: User,
        course_id: UUID,
        topic: str,
        interaction_type: str = "stepper",
        target_level: str | None = None,
        requirement: str | None = None,
        tool_context: ToolContext | None = None,
    ) -> dict[str, Any]:
        await CourseService(self.db).get_readable_course(course_id, current_user)
        brief = await MultimodalBriefService(self.db).build_brief(
            current_user=current_user,
            course_id=course_id,
            topic=topic,
            modality="interactive_courseware",
            requirement=requirement or target_level,
        )
        renderer = CoursewareService()
        spec = renderer.build_spec(topic=topic, interaction_type=interaction_type, brief=brief)
        rendered = renderer.render(spec)
        path, file_size, mime = self.storage.save_text(text=rendered.html, asset_type="courseware", suffix=".html")
        resource = await self.resources.create(
            user_id=current_user.id,
            course_id=course_id,
            knowledge_id=None,
            wiki_page_id=None,
            resource_type="interactive_courseware",
            title=rendered.title,
            content="已生成安全模板化互动课件，可在 sandbox iframe 中打开。",
            citations=brief["citations"],
            personalized_reason=brief.get("style_hint"),
            model_name="template-courseware-v1",
            prompt_version_id=None,
        )
        asset = await self.media.create_asset(
            user_id=current_user.id,
            course_id=course_id,
            resource_id=resource.id,
            agent_task_id=tool_context.task_id if tool_context else None,
            conversation_id=tool_context.conversation_id if tool_context else None,
            tool_call_id=tool_context.tool_call_id if tool_context else None,
            asset_type="html",
            title=rendered.title,
            description=resource.content,
            storage_path=path,
            mime_type=mime,
            file_size=file_size,
            provider="courseware_template",
            model_name="courseware-template-v1",
            citations=brief["citations"],
            safety_result=rendered.safety_result,
            render_meta={"spec": rendered.spec, "interaction_type": interaction_type},
        )
        await self.db.commit()
        return self._asset_response(asset, resource_id=resource.id, extra={"subtype": "courseware"})

    async def enqueue_video_job(self, job_id: UUID) -> None:
        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await redis.enqueue_job("run_multimodal_video_job", str(job_id))
        await redis.close()

    def _image_prompt(
        self,
        topic: str,
        image_type: str,
        style: str | None,
        requirement: str | None,
        brief: dict[str, Any],
    ) -> str:
        return (
            f"为大学课程生成教学插图。主题：{topic}\n"
            f"图片类型：{image_type}\n"
            f"风格：{style or brief.get('style_hint')}\n"
            f"要求：{requirement or ''}\n"
            f"必须表达的课程依据：\n{brief.get('source_summary') or ''}\n"
            "不要生成真实人物、商标、政治敏感元素。画面应简洁、教育用途、适合课堂展示。"
        )

    def _asset_response(
        self,
        asset,
        *,
        resource_id: UUID | None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = {
            "asset_id": str(asset.id),
            "resource_id": str(resource_id) if resource_id else None,
            "asset_type": asset.asset_type,
            "title": asset.title,
            "mime_type": asset.mime_type,
            "file_size": asset.file_size,
            "file_url": f"/api/v1/media-assets/{asset.id}/file",
            "citations": asset.citations,
            "safety_result": asset.safety_result,
        }
        data.update(extra or {})
        return data
