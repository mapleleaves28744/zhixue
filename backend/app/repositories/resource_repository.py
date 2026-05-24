from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resource import GeneratedResource


class ResourceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        knowledge_id: UUID | None,
        wiki_page_id: UUID | None,
        resource_type: str,
        title: str,
        content: str,
        citations: list[Any],
        personalized_reason: str | None,
        model_name: str | None,
        prompt_version_id: UUID | None,
    ) -> GeneratedResource:
        resource = GeneratedResource(
            user_id=user_id,
            course_id=course_id,
            knowledge_id=knowledge_id,
            wiki_page_id=wiki_page_id,
            resource_type=resource_type,
            title=title,
            content=content,
            citations=citations,
            personalized_reason=personalized_reason,
            model_name=model_name,
            prompt_version_id=prompt_version_id,
            status="active",
        )
        self.db.add(resource)
        await self.db.flush()
        await self.db.refresh(resource)
        return resource

    async def get_by_id(self, resource_id: UUID) -> GeneratedResource | None:
        result = await self.db.execute(
            select(GeneratedResource).where(GeneratedResource.id == resource_id)
        )
        return result.scalar_one_or_none()

    async def list_resources(
        self,
        *,
        user_id: UUID,
        course_id: UUID | None,
        resource_type: str | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[GeneratedResource], int]:
        stmt = select(GeneratedResource).where(GeneratedResource.user_id == user_id)
        if course_id is not None:
            stmt = stmt.where(GeneratedResource.course_id == course_id)
        if resource_type is not None:
            stmt = stmt.where(GeneratedResource.resource_type == resource_type)
        if status is not None:
            stmt = stmt.where(GeneratedResource.status == status)

        total = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        result = await self.db.execute(
            stmt.order_by(GeneratedResource.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), int(total or 0)

    async def archive(self, resource: GeneratedResource) -> GeneratedResource:
        resource.status = "archived"
        await self.db.flush()
        await self.db.refresh(resource)
        return resource

    async def mark_saved_to_wiki(
        self,
        resource: GeneratedResource,
        wiki_page_id: UUID,
    ) -> GeneratedResource:
        resource.status = "saved_to_wiki"
        resource.wiki_page_id = wiki_page_id
        await self.db.flush()
        await self.db.refresh(resource)
        return resource
