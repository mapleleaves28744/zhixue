from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course


class CourseRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        owner_id: UUID,
        title: str,
        course_code: str | None,
        description: str | None,
        subject: str | None,
        cover_url: str | None,
        visibility: str,
    ) -> Course:
        course = Course(
            owner_id=owner_id,
            title=title,
            course_code=course_code,
            description=description,
            subject=subject,
            cover_url=cover_url,
            visibility=visibility,
            status="active",
        )
        self.db.add(course)
        await self.db.flush()
        await self.db.refresh(course)
        return course

    async def list_courses(
        self,
        owner_id: UUID | None,
        status: str,
        page: int,
        page_size: int,
    ) -> tuple[list[Course], int]:
        statement = self._filtered_statement(owner_id, status)
        total_statement = select(func.count()).select_from(statement.subquery())
        total = await self.db.scalar(total_statement)

        result = await self.db.execute(
            statement.order_by(Course.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), int(total or 0)

    async def get_by_id(self, course_id: UUID) -> Course | None:
        result = await self.db.execute(select(Course).where(Course.id == course_id))
        return result.scalar_one_or_none()

    async def update(self, course: Course, values: dict[str, object]) -> Course:
        for key, value in values.items():
            setattr(course, key, value)
        course.updated_at = await self.db.scalar(select(func.now()))
        await self.db.flush()
        await self.db.refresh(course)
        return course

    async def archive(self, course: Course) -> Course:
        course.status = "archived"
        course.updated_at = await self.db.scalar(select(func.now()))
        await self.db.flush()
        await self.db.refresh(course)
        return course

    def _filtered_statement(self, owner_id: UUID | None, status: str) -> Select[tuple[Course]]:
        statement = select(Course)
        if owner_id is not None:
            statement = statement.where(Course.owner_id == owner_id)
        if status != "all":
            statement = statement.where(Course.status == status)
        return statement
