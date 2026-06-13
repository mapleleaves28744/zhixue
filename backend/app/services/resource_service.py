from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.course import Course
from app.models.knowledge import KnowledgePoint
from app.models.resource import GeneratedResource
from app.models.user import User
from app.models.wiki import WikiPage
from app.repositories.course_repository import CourseRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.media_repository import MediaRepository
from app.repositories.resource_repository import ResourceRepository
from app.repositories.wiki_repository import WikiRepository
from app.schemas.resource import (
    RESOURCE_TYPE_ALIASES,
    VALID_RESOURCE_TYPES,
    GeneratedResourceRead,
    ResourceGenerateRequest,
    ResourceGenerateResponse,
    ResourceSaveToWikiRequest,
)
from app.services.agent_service import AgentService
from app.services.course_service import CourseService
from app.services.immersive_classroom_service import CLASSROOM_MIME_TYPE
from app.services.resource_media_service import ResourceMediaService
from app.utils.mermaid_util import is_mermaid_code


MEDIA_PIPELINE_TYPES = frozenset(
    {
        "video",
        "animation",
        "interactive_courseware",
        "immersive_classroom",
        "mindmap",
        "diagram",
        "image",
    }
)


class ResourceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.courses = CourseRepository(db)
        self.knowledge = KnowledgeRepository(db)
        self.resources = ResourceRepository(db)
        self.wiki = WikiRepository(db)

    async def generate_resource(
        self,
        *,
        payload: ResourceGenerateRequest,
        current_user: User,
    ) -> ResourceGenerateResponse:
        course = await self._get_accessible_course(payload.course_id, current_user)
        resource_type = self._normalize_resource_type(payload.resource_type)
        if payload.save_to_wiki and payload.wiki_page_id is None:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="save_to_wiki=true 时必须提供 wiki_page_id",
                status_code=400,
            )

        knowledge = await self._get_knowledge(payload.knowledge_id, course, current_user)
        wiki_page = await self._get_readable_wiki_page(payload.wiki_page_id, course, current_user)

        if resource_type in MEDIA_PIPELINE_TYPES:
            return await self._generate_media_resource(
                payload=payload,
                current_user=current_user,
                course=course,
                resource_type=resource_type,
                knowledge=knowledge,
                wiki_page=wiki_page,
            )

        result = await AgentService(self.db).run_task(
            task_type="generate_resource",
            user_id=current_user.id,
            course_id=course.id,
            params={
                "knowledge_id": str(knowledge.id) if knowledge else None,
                "wiki_page_id": str(wiki_page.id) if wiki_page else None,
                "knowledge_name": knowledge.name if knowledge else None,
                "resource_type": resource_type,
                "requirement": payload.requirement,
                "use_profile": payload.use_profile,
            },
        )
        if not result.success:
            raise BusinessException(
                code=ErrorCode.AGENT_RUN_FAILED,
                detail=result.message,
                status_code=500,
            )

        data = result.data
        content = str(data.get("content") or "").strip()
        if not content:
            raise BusinessException(
                code=ErrorCode.LLM_CALL_FAILED,
                detail="资源生成结果为空",
                status_code=500,
            )

        review_result = await self._review_generated_content(
            user_id=current_user.id,
            course_id=course.id,
            content=content,
            citations=data.get("citations") or [],
        )

        resource = await self.resources.create(
            user_id=current_user.id,
            course_id=course.id,
            knowledge_id=knowledge.id if knowledge else None,
            wiki_page_id=wiki_page.id if wiki_page else None,
            resource_type=resource_type,
            title=str(data.get("title") or self._default_title(resource_type, knowledge, wiki_page))[:255],
            content=content,
            citations=self._ensure_list(data.get("citations")),
            personalized_reason=str(data.get("personalized_reason") or "") or None,
            model_name=str(data.get("model_name") or "") or None,
            prompt_version_id=self._uuid(data.get("prompt_version_id")),
        )
        await ResourceMediaService(self.db).enrich_after_generate(
            resource=resource,
            current_user=current_user,
            resource_type=resource_type,
            requirement=payload.requirement,
        )
        await self.db.commit()
        await self.db.refresh(resource)

        if payload.save_to_wiki:
            await self.save_to_wiki(
                resource_id=resource.id,
                current_user=current_user,
                payload=ResourceSaveToWikiRequest(wiki_page_id=wiki_page.id),
            )
            refreshed = await self.resources.get_by_id(resource.id)
            if refreshed is not None:
                resource = refreshed

        response_data = await self._with_media_fields(resource, current_user.id)
        response_data.update(
            {
                "resource_id": resource.id,
                "id": resource.id,
                "agent_run_id": self._uuid(data.get("agent_run_id")),
                "review_result": review_result,
            }
        )
        return ResourceGenerateResponse.model_validate(response_data)

    async def list_resources(
        self,
        *,
        current_user: User,
        course_id: UUID | None,
        resource_type: str | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[GeneratedResourceRead], int]:
        if course_id is not None:
            await self._get_accessible_course(course_id, current_user)
        normalized_type = self._normalize_resource_type(resource_type) if resource_type else None
        normalized_status = None if status == "all" else status
        items, total = await self.resources.list_resources(
            user_id=current_user.id,
            course_id=course_id,
            resource_type=normalized_type,
            status=normalized_status,
            page=page,
            page_size=page_size,
        )
        enriched: list[GeneratedResourceRead] = []
        for item in items:
            payload = await self._with_media_fields(item, current_user.id)
            enriched.append(GeneratedResourceRead.model_validate(payload))
        return enriched, total

    async def get_resource(
        self,
        *,
        resource_id: UUID,
        current_user: User,
    ) -> GeneratedResourceRead:
        resource = await self._get_owned_resource(resource_id, current_user.id)
        data = await self._with_media_fields(resource, current_user.id)
        return GeneratedResourceRead.model_validate(data)

    async def archive_resource(
        self,
        *,
        resource_id: UUID,
        current_user: User,
    ) -> GeneratedResourceRead:
        resource = await self._get_owned_resource(resource_id, current_user.id)
        resource = await self.resources.archive(resource)
        await self.db.commit()
        await self.db.refresh(resource)
        return GeneratedResourceRead.model_validate(resource)

    async def save_to_wiki(
        self,
        *,
        resource_id: UUID,
        current_user: User,
        payload: ResourceSaveToWikiRequest,
    ) -> dict[str, Any]:
        resource = await self._get_owned_resource(resource_id, current_user.id)
        if resource.status == "archived":
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="已归档的资源不能保存到 Wiki",
                status_code=400,
            )

        target_page_id = payload.wiki_page_id or resource.wiki_page_id
        if target_page_id is None:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="缺少目标 Wiki 页面 ID",
                status_code=400,
            )
        course = await self._get_accessible_course(resource.course_id, current_user)
        page = await self._get_writable_or_personal_copy(target_page_id, course, current_user)
        if page.status == "archived":
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="已归档的 Wiki 页面不可更新",
                status_code=400,
            )

        section_title = payload.section_title or f"AI 生成资源：{resource.title}"
        appended = self._format_resource_for_wiki(resource, section_title)
        new_content = f"{page.content.rstrip()}\n\n---\n\n{appended}"
        new_version = page.current_version + 1

        await self.wiki.update_page(
            page,
            content=new_content,
            current_version=new_version,
        )
        await self.wiki.create_version(
            page_id=page.id,
            version_number=new_version,
            title=page.title,
            content=new_content,
            summary=page.summary,
            change_message=f"保存学习资源：{resource.title}",
            created_by=current_user.id,
        )
        await self.wiki.create_source(
            page_id=page.id,
            source_type="resource",
            source_id=resource.id,
            source_title=resource.title,
            quote_text=resource.content[:200],
        )
        await self.resources.mark_saved_to_wiki(resource, page.id)
        await self.db.commit()
        await self.db.refresh(resource)
        await self.db.refresh(page)

        return {
            "resource": GeneratedResourceRead.model_validate(resource).model_dump(mode="json"),
            "wiki_page": {
                "id": str(page.id),
                "title": page.title,
                "current_version": page.current_version,
            },
        }

    async def _review_generated_content(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        content: str,
        citations: list[Any],
    ) -> dict[str, Any]:
        review = await AgentService(self.db).run_task(
            task_type="review_content",
            user_id=user_id,
            course_id=course_id,
            params={
                "content": (
                    f"{content[:3500]}\n\n"
                    f"引用来源数量：{len(citations)}；引用来源：{citations[:5]}"
                )
            },
        )
        if review.success:
            return review.data
        return {
            "pass": bool(citations),
            "risk_level": "medium",
            "issues": [review.message],
            "revision_suggestions": "Review Agent 未完成，已按来源数量做规则兜底。",
        }

    async def _get_accessible_course(self, course_id: UUID, current_user: User) -> Course:
        return await CourseService(self.db).get_readable_course(course_id, current_user)

    async def _get_knowledge(
        self,
        knowledge_id: UUID | None,
        course: Course,
        current_user: User,
    ) -> KnowledgePoint | None:
        if knowledge_id is None:
            return None
        items = await self.knowledge.list_visible_by_course(
            course_id=course.id,
            current_user_id=current_user.id,
            public_owner_id=course.owner_id if course.visibility == "public_template" else None,
            include_all=current_user.role == "admin",
        )
        for item in items:
            if item.id == knowledge_id:
                return item
        raise BusinessException(
            code=ErrorCode.NOT_FOUND,
            detail="知识点不存在",
            status_code=404,
        )

    async def _get_readable_wiki_page(
        self,
        wiki_page_id: UUID | None,
        course: Course,
        current_user: User,
    ) -> WikiPage | None:
        if wiki_page_id is None:
            return None
        page = await self.wiki.get_by_id_simple(wiki_page_id)
        if page is None or page.course_id != course.id:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="Wiki 页面不存在",
                status_code=404,
            )
        if page.status == "archived":
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="已归档的 Wiki 页面不可使用",
                status_code=400,
            )
        if current_user.role == "admin" or page.owner_id == current_user.id:
            return page
        is_public_page = (
            course.visibility == "public_template"
            and page.owner_id == course.owner_id
        )
        if is_public_page:
            return page
        raise BusinessException(
            code=ErrorCode.NOT_FOUND,
            detail="Wiki 页面不存在",
            status_code=404,
        )

    async def _get_writable_or_personal_copy(
        self,
        wiki_page_id: UUID,
        course: Course,
        current_user: User,
    ) -> WikiPage:
        page = await self._get_readable_wiki_page(wiki_page_id, course, current_user)
        if current_user.role == "admin" or page.owner_id == current_user.id:
            return page

        is_public_page = (
            course.visibility == "public_template"
            and page.owner_id == course.owner_id
        )
        if not is_public_page:
            raise BusinessException(
                code=ErrorCode.FORBIDDEN,
                detail="无权编辑此 Wiki 页面",
                status_code=403,
            )
        copied = await self.wiki.create_page(
            course_id=course.id,
            owner_id=current_user.id,
            title=page.title,
            content=page.content,
            summary=page.summary,
        )
        await self.wiki.create_source(
            page_id=copied.id,
            source_type="manual",
            source_id=page.id,
            source_title=f"个人副本来源：{page.title}",
            quote_text=(page.summary or page.content[:200]),
        )
        return copied

    async def _generate_media_resource(
        self,
        *,
        payload: ResourceGenerateRequest,
        current_user: User,
        course: Course,
        resource_type: str,
        knowledge: KnowledgePoint | None,
        wiki_page: WikiPage | None,
    ) -> ResourceGenerateResponse:
        from app.services.immersive_classroom_service import ImmersiveClassroomService
        from app.services.multimodal_resource_service import MultimodalResourceService

        topic = self._resolve_generation_topic(knowledge, wiki_page, payload.requirement)
        requirement = payload.requirement
        multimodal = MultimodalResourceService(self.db)

        media_job_id: UUID | None = None
        job_status: str | None = None
        job_message: str | None = None

        if resource_type in {"video", "animation"}:
            result = await multimodal.create_video_job(
                current_user=current_user,
                course_id=course.id,
                topic=topic,
                target_level=requirement,
                resource_type=resource_type,
            )
            media_job_id = self._uuid(result.get("job_id"))
            job_status = str(result.get("status") or "queued")
            job_message = str(result.get("message") or "")
            resource = await self._get_owned_resource(UUID(str(result["resource_id"])), current_user.id)
        elif resource_type == "immersive_classroom":
            result = await ImmersiveClassroomService(self.db).create_job(
                current_user=current_user,
                course_id=course.id,
                topic=topic,
                learning_goal=requirement,
            )
            media_job_id = self._uuid(result.get("job_id"))
            job_status = str(result.get("status") or "queued")
            job_message = str(result.get("message") or "")
            resource = await self._get_owned_resource(UUID(str(result["resource_id"])), current_user.id)
        elif resource_type == "interactive_courseware":
            result = await multimodal.generate_courseware(
                current_user=current_user,
                course_id=course.id,
                topic=topic,
                requirement=requirement,
                target_level=requirement,
            )
            resource = await self._get_owned_resource(UUID(str(result["resource_id"])), current_user.id)
        elif resource_type in {"mindmap", "diagram", "image"}:
            image_type_map = {
                "mindmap": "mindmap",
                "diagram": "process_visual",
                "image": "concept_illustration",
            }
            result = await multimodal.generate_image(
                current_user=current_user,
                course_id=course.id,
                topic=topic,
                image_type=image_type_map.get(resource_type, "concept_illustration"),
                requirement=requirement,
            )
            resource = await self._get_owned_resource(UUID(str(result["resource_id"])), current_user.id)
            if resource.resource_type != "image":
                resource.resource_type = "image"
                await self.db.flush()
                await self.db.commit()
                await self.db.refresh(resource)
        else:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail=f"不支持的媒体资源类型: {resource_type}",
                status_code=400,
            )

        if payload.save_to_wiki and wiki_page is not None:
            await self.save_to_wiki(
                resource_id=resource.id,
                current_user=current_user,
                payload=ResourceSaveToWikiRequest(wiki_page_id=wiki_page.id),
            )
            refreshed = await self.resources.get_by_id(resource.id)
            if refreshed is not None:
                resource = refreshed

        return await self._build_generate_response(
            resource=resource,
            user_id=current_user.id,
            media_job_id=media_job_id,
            job_status=job_status,
            job_message=job_message,
        )

    async def _build_generate_response(
        self,
        *,
        resource: GeneratedResource,
        user_id: UUID,
        media_job_id: UUID | None = None,
        job_status: str | None = None,
        job_message: str | None = None,
        agent_run_id: UUID | None = None,
        review_result: dict[str, Any] | None = None,
    ) -> ResourceGenerateResponse:
        response_data = await self._with_media_fields(resource, user_id)
        response_data.update(
            {
                "resource_id": resource.id,
                "id": resource.id,
                "agent_run_id": agent_run_id,
                "review_result": review_result
                or {"passed": True, "risk_level": "low", "mode": "media_pipeline"},
                "media_job_id": media_job_id,
                "job_status": job_status,
                "job_message": job_message,
            }
        )
        return ResourceGenerateResponse.model_validate(response_data)

    @staticmethod
    def _resolve_generation_topic(
        knowledge: KnowledgePoint | None,
        wiki_page: WikiPage | None,
        requirement: str | None,
    ) -> str:
        if knowledge is not None and knowledge.name.strip():
            return knowledge.name.strip()
        if wiki_page is not None and wiki_page.title.strip():
            return wiki_page.title.strip()
        if requirement and requirement.strip():
            return requirement.strip()[:80]
        return "数据结构"

    async def _with_media_fields(self, resource: GeneratedResource, user_id: UUID) -> dict[str, Any]:
        media_repo = MediaRepository(self.db)
        data = GeneratedResourceRead.model_validate(resource).model_dump(mode="json")
        if resource.resource_type == "immersive_classroom":
            assets = await media_repo.list_assets_for_resource(resource.id, user_id)
            classroom_asset = next(
                (
                    item
                    for item in assets
                    if item.asset_type == "interactive_classroom"
                    or str(item.mime_type or "") == CLASSROOM_MIME_TYPE
                ),
                None,
            )
            video_asset = next(
                (
                    item
                    for item in reversed(assets)
                    if item.asset_type == "video" or str(item.mime_type or "").startswith("video/")
                ),
                None,
            )
            primary = classroom_asset or video_asset
            if classroom_asset is not None:
                data["media_asset_id"] = str(classroom_asset.id)
                data["media_mime_type"] = classroom_asset.mime_type
                data["media_asset_type"] = classroom_asset.asset_type
                data["media_file_url"] = f"/api/v1/media-assets/{classroom_asset.id}/file"
            elif primary is not None:
                data["media_asset_id"] = str(primary.id)
                data["media_mime_type"] = primary.mime_type
                data["media_asset_type"] = primary.asset_type
                data["media_file_url"] = f"/api/v1/media-assets/{primary.id}/file"
            if video_asset is not None:
                data["preview_video_asset_id"] = str(video_asset.id)
                data["preview_video_mime_type"] = video_asset.mime_type
            data["preview_mode"] = "immersive_classroom" if classroom_asset is not None else self._preview_mode(
                resource.resource_type, primary
            )
        else:
            asset = await media_repo.get_asset_for_resource(resource.id, user_id)
            if asset is not None:
                data["media_asset_id"] = str(asset.id)
                data["media_mime_type"] = asset.mime_type
                data["media_asset_type"] = asset.asset_type
                data["media_file_url"] = f"/api/v1/media-assets/{asset.id}/file"
            data["preview_mode"] = self._preview_mode(resource.resource_type, asset)
        if not data.get("media_asset_id"):
            job = await media_repo.get_latest_job_for_resource(resource.id, user_id)
            if job is not None and job.status in {"queued", "running"}:
                data["media_job_id"] = str(job.id)
                data["job_status"] = job.status
        data["content_format"] = "mermaid" if is_mermaid_code(resource.content) else "markdown"
        return data

    @staticmethod
    def _preview_mode(resource_type: str, asset: Any) -> str:
        if asset is not None:
            mime = str(asset.mime_type or "")
            if asset.asset_type == "video" or mime.startswith("video/"):
                return "video"
            if asset.asset_type == "audio" or mime.startswith("audio/"):
                return "audio"
            if asset.asset_type == "image" or mime.startswith("image/"):
                return "image"
            if asset.asset_type == "html" or mime.startswith("text/html"):
                return "html"
            if mime == CLASSROOM_MIME_TYPE:
                return "immersive_classroom"
        if resource_type in {"mindmap", "diagram"}:
            return "mermaid"
        if resource_type == "interactive_courseware":
            return "html"
        if resource_type == "immersive_classroom":
            return "immersive_classroom"
        return "text"

    async def _get_owned_resource(
        self,
        resource_id: UUID,
        user_id: UUID,
    ) -> GeneratedResource:
        resource = await self.resources.get_by_id(resource_id)
        if resource is None or resource.user_id != user_id:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="资源不存在",
                status_code=404,
            )
        return resource

    def _normalize_resource_type(self, value: str) -> str:
        cleaned = value.strip()
        normalized = RESOURCE_TYPE_ALIASES.get(cleaned, cleaned.lower())
        if normalized not in VALID_RESOURCE_TYPES:
            allowed = " / ".join(sorted(VALID_RESOURCE_TYPES))
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail=f"resource_type 只能是 {allowed}",
                status_code=400,
            )
        return normalized

    def _default_title(
        self,
        resource_type: str,
        knowledge: KnowledgePoint | None,
        wiki_page: WikiPage | None,
    ) -> str:
        labels = {
            "explanation": "讲解",
            "summary": "总结",
            "example": "例题",
            "flashcard": "复习卡",
            "review": "错题解析",
            "mindmap": "图片",
            "diagram": "图片",
            "image": "图片",
            "video": "讲解视频",
            "animation": "动画",
            "interactive_courseware": "互动课件",
            "immersive_classroom": "沉浸课堂",
            "code_project": "代码实操项目",
            "reading_pack": "拓展阅读包",
        }
        topic = knowledge.name if knowledge else wiki_page.title if wiki_page else "数据结构"
        return f"{topic}{labels[resource_type]}"

    def _ensure_list(self, value: object) -> list[Any]:
        return value if isinstance(value, list) else []

    def _uuid(self, value: object) -> UUID | None:
        if isinstance(value, UUID):
            return value
        if isinstance(value, str) and value:
            try:
                return UUID(value)
            except ValueError:
                return None
        return None

    def _format_resource_for_wiki(
        self,
        resource: GeneratedResource,
        section_title: str,
    ) -> str:
        citations = resource.citations or []
        citation_lines = []
        for citation in citations[:8]:
            if isinstance(citation, dict):
                title = citation.get("title") or citation.get("source_title") or "来源"
                source_type = citation.get("source_type") or "source"
                citation_lines.append(f"- [{source_type}] {title}")
        citation_text = "\n".join(citation_lines) if citation_lines else "- AI 推断内容，建议核对资料。"
        reason = resource.personalized_reason or "暂无个性化证据，建议结合学习记录继续校准。"
        return (
            f"## {section_title}\n\n"
            f"{resource.content}\n\n"
            "### 个性化原因\n\n"
            f"{reason}\n\n"
            "### 引用来源\n\n"
            f"{citation_text}"
        )
