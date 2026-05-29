from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgePoint


class KnowledgeRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        course_id: UUID,
        owner_id: UUID,
        scope: str,
        name: str,
        chapter: str | None = None,
        description: str | None = None,
        difficulty: str | None = None,
        importance: str | None = None,
        sort_order: int = 0,
    ) -> KnowledgePoint:
        point = KnowledgePoint(
            course_id=course_id,
            owner_id=owner_id,
            scope=scope,
            name=name,
            chapter=chapter,
            description=description,
            difficulty=difficulty,
            importance=importance,
            sort_order=sort_order,
        )
        self.db.add(point)
        await self.db.flush()
        await self.db.refresh(point)
        return point

    async def find_by_course_and_name(
        self, course_id: UUID, owner_id: UUID, name: str
    ) -> KnowledgePoint | None:
        result = await self.db.execute(
            select(KnowledgePoint).where(
                KnowledgePoint.course_id == course_id,
                KnowledgePoint.owner_id == owner_id,
                KnowledgePoint.name == name,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_course(self, course_id: UUID) -> list[KnowledgePoint]:
        result = await self.db.execute(
            select(KnowledgePoint)
            .where(KnowledgePoint.course_id == course_id)
            .order_by(KnowledgePoint.sort_order, KnowledgePoint.name)
        )
        return list(result.scalars().all())

    async def list_visible_by_course(
        self,
        *,
        course_id: UUID,
        current_user_id: UUID,
        public_owner_id: UUID | None,
        include_all: bool = False,
    ) -> list[KnowledgePoint]:
        statement = select(KnowledgePoint).where(KnowledgePoint.course_id == course_id)
        if not include_all:
            owner_ids = [current_user_id]
            if public_owner_id is not None and public_owner_id != current_user_id:
                owner_ids.append(public_owner_id)
            statement = statement.where(KnowledgePoint.owner_id.in_(owner_ids))
        result = await self.db.execute(
            statement.order_by(KnowledgePoint.sort_order, KnowledgePoint.name)
        )
        return list(result.scalars().all())

    async def list_by_owner(self, course_id: UUID, owner_id: UUID) -> list[KnowledgePoint]:
        result = await self.db.execute(
            select(KnowledgePoint)
            .where(
                KnowledgePoint.course_id == course_id,
                KnowledgePoint.owner_id == owner_id,
            )
            .order_by(KnowledgePoint.sort_order, KnowledgePoint.name)
        )
        return list(result.scalars().all())

    async def create_if_not_exists(
        self,
        course_id: UUID,
        owner_id: UUID,
        scope: str,
        name: str,
        chapter: str | None = None,
        description: str | None = None,
        difficulty: str | None = None,
        importance: str | None = None,
        sort_order: int = 0,
    ) -> tuple[KnowledgePoint, bool]:
        existing = await self.find_by_course_and_name(course_id, owner_id, name)
        if existing:
            return existing, False
        point = await self.create(
            course_id=course_id,
            owner_id=owner_id,
            scope=scope,
            name=name,
            chapter=chapter,
            description=description,
            difficulty=difficulty,
            importance=importance,
            sort_order=sort_order,
        )
        return point, True

    async def create_batch_if_not_exists(
        self,
        course_id: UUID,
        owner_id: UUID,
        scope: str,
        items: list[dict],
    ) -> tuple[list[KnowledgePoint], int]:
        created: list[KnowledgePoint] = []
        new_count = 0
        for i, item in enumerate(items):
            point, is_new = await self.create_if_not_exists(
                course_id=course_id,
                owner_id=owner_id,
                scope=scope,
                name=item["name"],
                chapter=item.get("chapter"),
                description=item.get("description"),
                difficulty=item.get("difficulty"),
                importance=item.get("importance"),
                sort_order=item.get("sort_order", i),
            )
            created.append(point)
            if is_new:
                new_count += 1
        return created, new_count
