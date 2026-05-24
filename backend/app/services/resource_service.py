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

        knowledge = await self._get_knowledge(payload.knowledge_id, course.id)
        wiki_page = await self._get_wiki_page(payload.wiki_page_id, current_user.id, course.id)

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

        return ResourceGenerateResponse(
            resource_id=resource.id,
            title=resource.title,
            content=resource.content,
            citations=resource.citations,
            personalized_reason=resource.personalized_reason,
            agent_run_id=self._uuid(data.get("agent_run_id")),
            review_result=review_result,
            status=resource.status,
            wiki_page_id=resource.wiki_page_id,
        )

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
        return [GeneratedResourceRead.model_validate(item) for item in items], total

    async def get_resource(
        self,
        *,
        resource_id: UUID,
        current_user: User,
    ) -> GeneratedResourceRead:
        resource = await self._get_owned_resource(resource_id, current_user.id)
        return GeneratedResourceRead.model_validate(resource)

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
        page = await self._get_wiki_page(target_page_id, current_user.id, resource.course_id)
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
        course = await self.courses.get_by_id(course_id)
        if course is None or (current_user.role != "admin" and course.owner_id != current_user.id):
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="课程不存在",
                status_code=404,
            )
        return course

    async def _get_knowledge(
        self,
        knowledge_id: UUID | None,
        course_id: UUID,
    ) -> KnowledgePoint | None:
        if knowledge_id is None:
            return None
        items = await self.knowledge.list_by_course(course_id)
        for item in items:
            if item.id == knowledge_id:
                return item
        raise BusinessException(
            code=ErrorCode.NOT_FOUND,
            detail="知识点不存在",
            status_code=404,
        )

    async def _get_wiki_page(
        self,
        wiki_page_id: UUID | None,
        owner_id: UUID,
        course_id: UUID,
    ) -> WikiPage | None:
        if wiki_page_id is None:
            return None
        page = await self.wiki.get_by_id_simple(wiki_page_id)
        if page is None or page.owner_id != owner_id or page.course_id != course_id:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="Wiki 页面不存在",
                status_code=404,
            )
        return page

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
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="resource_type 只能是 explanation / summary / example / flashcard / review",
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
