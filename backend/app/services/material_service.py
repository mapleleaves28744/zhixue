from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.material import CourseMaterial
from app.models.user import User
from app.repositories.course_repository import CourseRepository
from app.repositories.material_repository import MaterialRepository
from app.schemas.material import MaterialParseResult, MaterialRead, MaterialUploadResponse
from app.services.course_service import CourseService
from app.services.material_parse_service import MaterialParseService
from app.storage.local_storage import LocalMaterialStorage


ALLOWED_MATERIAL_TYPES = {"pdf", "docx", "md", "txt"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class MaterialService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.courses = CourseRepository(db)
        self.materials = MaterialRepository(db)
        self.storage = LocalMaterialStorage(settings.local_storage_root)

    async def upload_material(
        self,
        course_id: UUID,
        upload: UploadFile,
        current_user: User,
    ) -> MaterialUploadResponse:
        await self._ensure_course_read_access(course_id, current_user)
        original_name = Path(upload.filename or "").name
        if not original_name:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="文件名不能为空",
                status_code=400,
            )

        extension = self._extract_extension(original_name)
        material_id = uuid4()
        storage_path, file_size = await self.storage.save_upload(
            course_id=course_id,
            material_id=material_id,
            extension=extension,
            upload=upload,
            max_bytes=MAX_UPLOAD_BYTES,
        )

        material = await self.materials.create(
            material_id=material_id,
            course_id=course_id,
            uploaded_by=current_user.id,
            file_name=original_name,
            file_type=extension,
            file_size=file_size,
            storage_path=storage_path,
        )
        await self.db.commit()
        await self.db.refresh(material)
        return MaterialUploadResponse.model_validate(material)

    async def list_materials(
        self,
        course_id: UUID,
        current_user: User,
        page: int,
        page_size: int,
    ) -> tuple[list[MaterialRead], int]:
        course = await CourseService(self.db).get_readable_course(course_id, current_user)
        public_owner_id = course.owner_id if course.visibility == "public_template" else None
        materials, total = await self.materials.list_visible_by_course(
            course_id=course_id,
            current_user_id=current_user.id,
            public_owner_id=public_owner_id,
            include_all=current_user.role == "admin",
            page=page,
            page_size=page_size,
        )
        return [MaterialRead.model_validate(material) for material in materials], total

    async def get_material(self, material_id: UUID, current_user: User) -> MaterialRead:
        material = await self.get_readable_material(material_id, current_user)
        return MaterialRead.model_validate(material)

    async def get_parse_status(self, material_id: UUID, current_user: User) -> MaterialParseResult:
        material = await self.get_readable_material(material_id, current_user)
        return self._build_parse_result(material)

    async def parse_material(self, material_id: UUID, current_user: User) -> MaterialParseResult:
        material = await self.get_writable_material(material_id, current_user)
        return await MaterialParseService(self.db, self.storage).parse_material(material)

    async def get_readable_material(
        self,
        material_id: UUID,
        current_user: User,
    ) -> CourseMaterial:
        material = await self.materials.get_by_id(material_id)
        if material is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="资料不存在",
                status_code=404,
            )
        course = await CourseService(self.db).get_readable_course(material.course_id, current_user)
        if not self._can_read_material(material, course, current_user):
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="资料不存在",
                status_code=404,
            )
        return material

    async def get_writable_material(
        self,
        material_id: UUID,
        current_user: User,
    ) -> CourseMaterial:
        material = await self.materials.get_by_id(material_id)
        if material is None:
            raise BusinessException(
                code=ErrorCode.NOT_FOUND,
                detail="资料不存在",
                status_code=404,
            )
        course = await CourseService(self.db).get_readable_course(material.course_id, current_user)
        if not self._can_write_material(material, course, current_user):
            raise BusinessException(
                code=ErrorCode.FORBIDDEN,
                detail="公共资料只读，或当前用户无权操作该资料",
                status_code=403,
            )
        return material

    async def _get_accessible_material(
        self,
        material_id: UUID,
        current_user: User,
    ) -> CourseMaterial:
        return await self.get_readable_material(material_id, current_user)

    async def _ensure_course_read_access(self, course_id: UUID, current_user: User) -> None:
        await CourseService(self.db).get_readable_course(course_id, current_user)

    async def _ensure_course_write_access(self, course_id: UUID, current_user: User) -> None:
        await CourseService(self.db).get_writable_course(course_id, current_user)

    def _can_read_material(self, material: CourseMaterial, course: object, current_user: User) -> bool:
        if current_user.role == "admin":
            return True
        if material.uploaded_by == current_user.id:
            return True
        return (
            getattr(course, "visibility", None) == "public_template"
            and getattr(course, "status", None) == "active"
            and material.uploaded_by == getattr(course, "owner_id", None)
        )

    def _can_write_material(self, material: CourseMaterial, course: object, current_user: User) -> bool:
        if current_user.role == "admin":
            return True
        if material.uploaded_by == current_user.id:
            return True
        return (
            material.uploaded_by == getattr(course, "owner_id", None)
            and current_user.id == getattr(course, "owner_id", None)
        )

    def _extract_extension(self, file_name: str) -> str:
        extension = Path(file_name).suffix.lower().lstrip(".")
        if extension not in ALLOWED_MATERIAL_TYPES:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail="仅支持 pdf、docx、md、txt 格式资料",
                status_code=400,
            )
        return extension

    def _build_parse_result(self, material: CourseMaterial) -> MaterialParseResult:
        extra_meta = material.extra_meta or {}
        return MaterialParseResult(
            id=material.id,
            course_id=material.course_id,
            file_name=material.file_name,
            file_type=material.file_type,
            parse_status=material.parse_status,
            parse_error=material.parse_error,
            text_hash=material.text_hash,
            text_length=int(extra_meta.get("text_length") or 0),
            parsed_text_path=extra_meta.get("parsed_text_path"),
        )
