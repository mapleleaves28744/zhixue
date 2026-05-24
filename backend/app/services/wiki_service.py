from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.wiki import WikiPage, WikiPageVersion
from app.repositories.wiki_repository import WikiRepository

logger = logging.getLogger(__name__)


class WikiService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = WikiRepository(db)

    async def create_page(
        self,
        owner_id: UUID,
        course_id: UUID,
        title: str,
        content: str,
        summary: str | None = None,
    ) -> WikiPage:
        page = await self.repo.create_page(
            course_id=course_id,
            owner_id=owner_id,
            title=title,
            content=content,
            summary=summary,
        )
        await self.db.commit()
        await self.db.refresh(page)
        return page

    async def get_page(self, page_id: UUID, owner_id: UUID) -> WikiPage:
        page = await self.repo.get_by_id(page_id)
        if page is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="Wiki 页面不存在",
                status_code=404,
            )
        if page.owner_id != owner_id:
            raise BusinessException(
                code=ErrorCode.FORBIDDEN,
                detail="无权访问此 Wiki 页面",
                status_code=403,
            )
        return page

    async def list_pages(
        self,
        owner_id: UUID,
        course_id: UUID,
        status: str | None = "active",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[WikiPage], int]:
        return await self.repo.list_by_owner(
            owner_id=owner_id,
            course_id=course_id,
            status=status,
            page=page,
            page_size=page_size,
        )

    async def update_page(
        self,
        page_id: UUID,
        owner_id: UUID,
        title: str | None = None,
        content: str | None = None,
        summary: str | None = None,
        change_message: str | None = None,
    ) -> WikiPage:
        page = await self.get_page(page_id, owner_id)
        if page.status == "archived":
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="已归档的页面不可编辑",
                status_code=400,
            )

        new_title = title if title is not None else page.title
        new_content = content if content is not None else page.content
        new_summary = summary if summary is not None else page.summary
        new_version = page.current_version + 1

        await self.repo.update_page(
            page,
            title=new_title,
            content=new_content,
            summary=new_summary,
            current_version=new_version,
        )
        await self.repo.create_version(
            page_id=page.id,
            version_number=new_version,
            title=new_title,
            content=new_content,
            summary=new_summary,
            change_message=change_message or f"v{new_version} 更新",
            created_by=owner_id,
        )
        await self.db.commit()
        await self.db.refresh(page)
        return page

    async def archive_page(self, page_id: UUID, owner_id: UUID) -> None:
        page = await self.get_page(page_id, owner_id)
        await self.repo.update_page(page, status="archived")
        await self.db.commit()

    async def list_versions(
        self, page_id: UUID, owner_id: UUID
    ) -> list[WikiPageVersion]:
        await self.get_page(page_id, owner_id)
        return await self.repo.list_versions(page_id)

    async def rollback(
        self, page_id: UUID, owner_id: UUID, version_number: int
    ) -> WikiPage:
        page = await self.get_page(page_id, owner_id)
        version = await self.repo.get_version(page_id, version_number)
        if version is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail=f"版本 v{version_number} 不存在",
                status_code=404,
            )

        new_version = page.current_version + 1
        await self.repo.update_page(
            page,
            title=version.title,
            content=version.content,
            summary=version.summary,
            current_version=new_version,
        )
        await self.repo.create_version(
            page_id=page.id,
            version_number=new_version,
            title=version.title,
            content=version.content,
            summary=version.summary,
            change_message=f"回滚到 v{version_number}",
            created_by=owner_id,
        )
        await self.db.commit()
        await self.db.refresh(page)
        return page
