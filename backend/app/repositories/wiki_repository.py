from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.wiki import WikiLink, WikiPage, WikiPageVersion, WikiSource


def _slugify(title: str) -> str:
    slug = title.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:255] or "page"


class WikiRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ---- Pages ----

    async def create_page(
        self,
        course_id: UUID,
        owner_id: UUID,
        title: str,
        content: str,
        summary: str | None = None,
        slug: str | None = None,
    ) -> WikiPage:
        if not slug:
            slug = _slugify(title)
            slug = await self._unique_slug(course_id, owner_id, slug)

        page = WikiPage(
            course_id=course_id,
            owner_id=owner_id,
            title=title,
            slug=slug,
            summary=summary,
            content=content,
            status="active",
            current_version=1,
        )
        self.db.add(page)
        await self.db.flush()
        await self.db.refresh(page)

        # Create initial version
        version = WikiPageVersion(
            page_id=page.id,
            version_number=1,
            title=title,
            content=content,
            summary=summary,
            change_message="初始创建",
            created_by=owner_id,
        )
        self.db.add(version)
        await self.db.flush()
        return page

    async def get_by_id(self, page_id: UUID) -> WikiPage | None:
        result = await self.db.execute(
            select(WikiPage)
            .options(selectinload(WikiPage.sources), selectinload(WikiPage.versions))
            .where(WikiPage.id == page_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_simple(self, page_id: UUID) -> WikiPage | None:
        result = await self.db.execute(
            select(WikiPage).where(WikiPage.id == page_id)
        )
        return result.scalar_one_or_none()

    async def list_by_owner(
        self,
        owner_id: UUID,
        course_id: UUID,
        status: str | None = "active",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[WikiPage], int]:
        query = select(WikiPage).where(
            WikiPage.owner_id == owner_id,
            WikiPage.course_id == course_id,
        )
        if status:
            query = query.where(WikiPage.status == status)

        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        items_q = (
            query.order_by(WikiPage.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(items_q)
        return list(result.scalars().all()), total

    async def update_page(self, page: WikiPage, **fields: object) -> WikiPage:
        for key, value in fields.items():
            setattr(page, key, value)
        await self.db.flush()
        await self.db.refresh(page)
        return page

    async def find_by_slug(
        self, course_id: UUID, owner_id: UUID, slug: str
    ) -> WikiPage | None:
        result = await self.db.execute(
            select(WikiPage).where(
                WikiPage.course_id == course_id,
                WikiPage.owner_id == owner_id,
                WikiPage.slug == slug,
            )
        )
        return result.scalar_one_or_none()

    async def _unique_slug(
        self, course_id: UUID, owner_id: UUID, base_slug: str
    ) -> str:
        slug = base_slug
        counter = 1
        while await self.find_by_slug(course_id, owner_id, slug):
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    # ---- Versions ----

    async def create_version(
        self,
        page_id: UUID,
        version_number: int,
        title: str,
        content: str,
        summary: str | None,
        change_message: str | None,
        created_by: UUID,
    ) -> WikiPageVersion:
        version = WikiPageVersion(
            page_id=page_id,
            version_number=version_number,
            title=title,
            content=content,
            summary=summary,
            change_message=change_message,
            created_by=created_by,
        )
        self.db.add(version)
        await self.db.flush()
        return version

    async def list_versions(self, page_id: UUID) -> list[WikiPageVersion]:
        result = await self.db.execute(
            select(WikiPageVersion)
            .where(WikiPageVersion.page_id == page_id)
            .order_by(WikiPageVersion.version_number.desc())
        )
        return list(result.scalars().all())

    async def get_version(
        self, page_id: UUID, version_number: int
    ) -> WikiPageVersion | None:
        result = await self.db.execute(
            select(WikiPageVersion).where(
                WikiPageVersion.page_id == page_id,
                WikiPageVersion.version_number == version_number,
            )
        )
        return result.scalar_one_or_none()

    # ---- Sources ----

    async def create_source(
        self,
        page_id: UUID,
        source_type: str,
        source_id: UUID,
        source_title: str | None = None,
        quote_text: str | None = None,
    ) -> WikiSource:
        source = WikiSource(
            page_id=page_id,
            source_type=source_type,
            source_id=source_id,
            source_title=source_title,
            quote_text=quote_text,
        )
        self.db.add(source)
        await self.db.flush()
        return source

    async def list_sources(self, page_id: UUID) -> list[WikiSource]:
        result = await self.db.execute(
            select(WikiSource).where(WikiSource.page_id == page_id)
        )
        return list(result.scalars().all())

    # ---- Links ----

    async def create_link(
        self,
        source_page_id: UUID,
        target_page_id: UUID,
        relation_type: str = "related",
    ) -> WikiLink | None:
        if source_page_id == target_page_id:
            return None
        existing = await self.db.execute(
            select(WikiLink).where(
                WikiLink.source_page_id == source_page_id,
                WikiLink.target_page_id == target_page_id,
                WikiLink.relation_type == relation_type,
            )
        )
        if existing.scalar_one_or_none():
            return None
        link = WikiLink(
            source_page_id=source_page_id,
            target_page_id=target_page_id,
            relation_type=relation_type,
        )
        self.db.add(link)
        await self.db.flush()
        return link

    async def list_links(self, page_id: UUID) -> list[WikiLink]:
        result = await self.db.execute(
            select(WikiLink).where(
                (WikiLink.source_page_id == page_id)
                | (WikiLink.target_page_id == page_id)
            )
        )
        return list(result.scalars().all())
