from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from arq.connections import RedisSettings, create_pool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.tools import ToolContext
from app.core.config import settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.user import User
from app.repositories.media_repository import MediaRepository
from app.repositories.resource_repository import ResourceRepository
from app.services.course_service import CourseService
from app.services.multimodal_brief_service import MultimodalBriefService


CLASSROOM_MIME_TYPE = "application/vnd.zhixue.openmaic-classroom+json"


class ImmersiveClassroomService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.media = MediaRepository(db)
        self.resources = ResourceRepository(db)

    async def create_job(
        self,
        *,
        current_user: User,
        course_id: UUID,
        topic: str,
        learning_goal: str | None = None,
        generate_video_export: bool = True,
        enable_images: bool = True,
        enable_video_clips: bool = False,
        enable_tts: bool = True,
        tool_context: ToolContext | None = None,
    ) -> dict[str, Any]:
        if not settings.openmaic_enabled:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="OpenMAIC 沉浸课堂引擎未启用，请配置 OPENMAIC_ENABLED=true",
                status_code=503,
            )
        course = await CourseService(self.db).get_readable_course(course_id, current_user)
        brief = await MultimodalBriefService(self.db).build_brief(
            current_user=current_user,
            course_id=course_id,
            topic=topic,
            modality="immersive_classroom",
            requirement=learning_goal,
            top_k=8,
        )
        requirement, context_text = self.build_classroom_context(
            course_title=course.title,
            topic=topic,
            learning_goal=learning_goal,
            brief=brief,
        )
        resource = await self.resources.create(
            user_id=current_user.id,
            course_id=course_id,
            knowledge_id=None,
            wiki_page_id=None,
            resource_type="immersive_classroom",
            title=f"{topic} 个性化沉浸课堂",
            content="沉浸课堂任务已创建，正在生成场景、媒体与配音。",
            citations=brief.get("citations") or [],
            personalized_reason=brief.get("style_hint"),
            model_name="openmaic",
            prompt_version_id=None,
        )
        payload = {
            "topic": topic,
            "learning_goal": learning_goal or "",
            "requirement": requirement,
            "context_text": context_text,
            "citations": brief.get("citations") or [],
            "personalized_reason": brief.get("style_hint"),
            "generate_video_export": generate_video_export,
            "enable_images": enable_images,
            "enable_video_clips": enable_video_clips,
            "enable_tts": enable_tts,
        }
        digest = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:20]
        idempotency_key = (
            tool_context.idempotency_key
            if tool_context
            else f"immersive-classroom:{current_user.id}:{course_id}:{digest}"
        )
        job = await self.media.create_job(
            user_id=current_user.id,
            course_id=course_id,
            resource_id=resource.id,
            job_type="immersive_classroom",
            idempotency_key=idempotency_key,
            provider="openmaic",
            input_payload=payload,
            agent_task_id=tool_context.task_id if tool_context else None,
            conversation_id=tool_context.conversation_id if tool_context else None,
            tool_call_id=tool_context.tool_call_id if tool_context else None,
        )
        await self.db.commit()
        await self.enqueue_job(job.id)
        return {
            "job_id": str(job.id),
            "resource_id": str(resource.id),
            "status": job.status,
            "stage": job.stage,
            "progress": job.progress,
            "message": "沉浸课堂任务已进入后台队列，可在 Agent 时间线查看进度。",
        }

    async def enqueue_job(self, job_id: UUID) -> None:
        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await redis.enqueue_job("run_immersive_classroom_job", str(job_id))
        await redis.close()

    @staticmethod
    def build_classroom_context(
        *,
        course_title: str,
        topic: str,
        learning_goal: str | None,
        brief: dict[str, Any],
    ) -> tuple[str, str]:
        profile = dict(brief.get("profile") or {})
        weak_names = [
            str(item.get("knowledge_name") or item.get("name") or "")
            for item in list(profile.get("weak_points") or [])[:5]
            if isinstance(item, dict)
        ]
        error_names = [
            str(item.get("pattern") or item.get("name") or "")
            for item in list(profile.get("error_patterns") or [])[:5]
            if isinstance(item, dict)
        ]
        requirement_lines = [
            f"为《{course_title}》课程生成一个围绕“{topic}”的中文个性化沉浸课堂。",
            f"学生目标：{learning_goal or profile.get('learning_goal') or '理解核心概念并能完成基础应用'}。",
            f"学生背景：{profile.get('grade') or '高校学生'}，专业：{profile.get('major') or '未指定'}。",
            f"讲解风格：{brief.get('style_hint') or '清晰、步骤化、适合大学课程'}。",
            f"需要重点补强：{'、'.join(filter(None, weak_names)) or '围绕当前主题识别易错点'}。",
            f"常见错误提醒：{'、'.join(filter(None, error_names)) or '根据课程依据指出常见误区'}。",
            "课堂应包含讲解幻灯片、至少一个互动场景、课堂小测和明确的讲解动作。",
            "重要结论必须来自所给课程依据；依据不足时明确说明，不得编造来源。",
        ]
        citation_lines: list[str] = []
        for index, item in enumerate(list(brief.get("citations") or [])[:8], start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "课程资料")[:160]
            page = f" 第{item['page_no']}页" if item.get("page_no") else ""
            quote_text = str(item.get("quote") or "")[:500]
            citation_lines.append(f"[{index}] {title}{page}\n{quote_text}")
        context_text = (
            f"课程：{course_title}\n主题：{topic}\n\n课程依据：\n"
            + ("\n\n".join(citation_lines) or "当前没有足够课程引用，请在课堂中明确标记需核对内容。")
        )
        return "\n".join(requirement_lines)[:5000], context_text[:12000]

    @staticmethod
    def classroom_asset_ref(
        *,
        asset_id: str,
        title: str,
        scenes_count: int,
        citation_count: int = 0,
        personalized_reason: str | None = None,
    ) -> dict[str, Any]:
        return {
            "type": "media_asset",
            "subtype": "immersive_classroom",
            "asset_id": asset_id,
            "title": title,
            "mime_type": CLASSROOM_MIME_TYPE,
            "scenes_count": scenes_count,
            "citation_count": citation_count,
            "personalized_reason": personalized_reason,
        }
