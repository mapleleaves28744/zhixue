from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material import CourseMaterial


class MaterialRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        material_id: UUID,
        course_id: UUID,
        uploaded_by: UUID,
        file_name: str,
        file_type: str,
        file_size: int,
        storage_path: str,
    ) -> CourseMaterial:
        material = CourseMaterial(
            id=material_id,
            course_id=course_id,
            uploaded_by=uploaded_by,
            file_name=file_name,
            file_type=file_type,
            file_size=file_size,
            storage_path=storage_path,
            parse_status="pending",
            extra_meta={},
        )
        self.db.add(material)
        await self.db.flush()
        await self.db.refresh(material)
        return material

    async def list_by_course(
        self,
        course_id: UUID,
        page: int,
        page_size: int,
    ) -> tuple[list[CourseMaterial], int]:
        statement = select(CourseMaterial).where(CourseMaterial.course_id == course_id)
        total_statement = select(func.count()).select_from(statement.subquery())
        total = await self.db.scalar(total_statement)
        result = await self.db.execute(
            statement.order_by(CourseMaterial.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), int(total or 0)

    async def list_visible_by_course(
        self,
        *,
        course_id: UUID,
        current_user_id: UUID,
        public_owner_id: UUID | None,
        include_all: bool = False,
        page: int,
        page_size: int,
    ) -> tuple[list[CourseMaterial], int]:
        statement = select(CourseMaterial).where(CourseMaterial.course_id == course_id)
        if not include_all:
            visible_owner_ids = [current_user_id]
            if public_owner_id is not None and public_owner_id != current_user_id:
                visible_owner_ids.append(public_owner_id)
            statement = statement.where(CourseMaterial.uploaded_by.in_(visible_owner_ids))

        total_statement = select(func.count()).select_from(statement.subquery())
        total = await self.db.scalar(total_statement)
        result = await self.db.execute(
            statement.order_by(CourseMaterial.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), int(total or 0)

    async def get_by_id(self, material_id: UUID) -> CourseMaterial | None:
        result = await self.db.execute(
            select(CourseMaterial).where(CourseMaterial.id == material_id)
        )
        return result.scalar_one_or_none()

    async def update(self, material: CourseMaterial, values: dict[str, object]) -> CourseMaterial:
        for key, value in values.items():
            setattr(material, key, value)
        material.updated_at = await self.db.scalar(select(func.now()))
        await self.db.flush()
        await self.db.refresh(material)
        return material

    def _course_statement(self, course_id: UUID) -> Select[tuple[CourseMaterial]]:
        return select(CourseMaterial).where(CourseMaterial.course_id == course_id)
