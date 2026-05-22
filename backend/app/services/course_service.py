from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.course import Course
from app.models.user import User
from app.repositories.course_repository import CourseRepository
from app.schemas.course import CourseCreate, CourseRead, CourseUpdate


class CourseService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.courses = CourseRepository(db)

    async def create_course(self, payload: CourseCreate, current_user: User) -> CourseRead:
        visibility = payload.visibility
        if current_user.role != "admin":
            visibility = "private"

        course = await self.courses.create(
            owner_id=current_user.id,
            title=self._clean_required_text(payload.title, "课程标题不能为空"),
            course_code=self._clean_optional_text(payload.course_code),
            description=self._clean_optional_text(payload.description),
            subject=self._clean_optional_text(payload.subject),
            cover_url=self._clean_optional_text(payload.cover_url),
            visibility=visibility,
        )
        await self.db.commit()
        await self.db.refresh(course)
        return CourseRead.model_validate(course)

    async def list_courses(
        self,
        current_user: User,
        page: int,
        page_size: int,
        status: str,
    ) -> tuple[list[CourseRead], int]:
        owner_id = None if current_user.role == "admin" else current_user.id
        courses, total = await self.courses.list_courses(
            owner_id=owner_id,
            status=status,
            page=page,
            page_size=page_size,
        )
        return [CourseRead.model_validate(course) for course in courses], total

    async def get_course(self, course_id: UUID, current_user: User) -> CourseRead:
        course = await self._get_accessible_course(course_id, current_user)
        return CourseRead.model_validate(course)

    async def update_course(
        self,
        course_id: UUID,
        payload: CourseUpdate,
        current_user: User,
    ) -> CourseRead:
        course = await self._get_accessible_course(course_id, current_user)
        values = payload.model_dump(exclude_unset=True)
        values = {
            key: self._clean_optional_text(value) if isinstance(value, str) else value
            for key, value in values.items()
        }
        if "title" in values and isinstance(values["title"], str):
            values["title"] = self._clean_required_text(
                values["title"],
                "课程标题不能为空",
            )

        if current_user.role != "admin":
            values.pop("visibility", None)

        if not values:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="没有可更新的字段",
                status_code=400,
            )

        course = await self.courses.update(course, values)
        await self.db.commit()
        await self.db.refresh(course)
        return CourseRead.model_validate(course)

    async def archive_course(self, course_id: UUID, current_user: User) -> CourseRead:
        course = await self._get_accessible_course(course_id, current_user)
        course = await self.courses.archive(course)
        await self.db.commit()
        await self.db.refresh(course)
        return CourseRead.model_validate(course)

    async def _get_accessible_course(self, course_id: UUID, current_user: User) -> Course:
        course = await self.courses.get_by_id(course_id)
        if course is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="课程不存在",
                status_code=404,
            )

        if current_user.role != "admin" and course.owner_id != current_user.id:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="课程不存在",
                status_code=404,
            )
        return course

    def _clean_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    def _clean_required_text(self, value: str, detail: str) -> str:
        value = value.strip()
        if not value:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail=detail,
                status_code=400,
            )
        return value
