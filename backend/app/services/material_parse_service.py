from hashlib import sha256
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.models.material import CourseMaterial
from app.repositories.material_repository import MaterialRepository
from app.schemas.material import MaterialParseResult
from app.services.chunk_service import ChunkService
from app.storage.local_storage import LocalMaterialStorage
from app.utils.document_parser import parse_document_text


class MaterialParseService:
    def __init__(self, db: AsyncSession, storage: LocalMaterialStorage) -> None:
        self.db = db
        self.materials = MaterialRepository(db)
        self.storage = storage

    async def parse_material(self, material: CourseMaterial) -> MaterialParseResult:
        await self.materials.update(
            material,
            {
                "parse_status": "processing",
                "parse_error": None,
            },
        )
        await self.db.commit()
        await self.db.refresh(material)

        try:
            text = parse_document_text(material.storage_path, material.file_type).strip()
            if not text:
                raise ValueError("未提取到有效文本")
            text_hash = sha256(text.encode("utf-8")).hexdigest()
            parsed_text_path = self.storage.write_parsed_text(material.course_id, material.id, text)
            extra_meta = dict(material.extra_meta or {})
            extra_meta.update(
                {
                    "parsed_text_path": parsed_text_path,
                    "text_length": len(text),
                }
            )
            await self.materials.update(
                material,
                {
                    "parse_status": "success",
                    "parse_error": None,
                    "text_hash": text_hash,
                    "extra_meta": extra_meta,
                },
            )
            await self.db.commit()
            await self.db.refresh(material)

            # Auto-chunk after successful parsing
            try:
                await ChunkService(self.db).chunk_material(material)
            except Exception:
                # Chunking failure should not fail the parse operation
                pass

            return self._build_result(material)
        except Exception as exc:
            await self.materials.update(
                material,
                {
                    "parse_status": "failed",
                    "parse_error": str(exc),
                },
            )
            await self.db.commit()
            await self.db.refresh(material)
            raise BusinessException(
                code=ErrorCode.FILE_PARSE_FAILED,
                detail=str(exc),
                status_code=500,
            ) from exc

    def _build_result(self, material: CourseMaterial) -> MaterialParseResult:
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
