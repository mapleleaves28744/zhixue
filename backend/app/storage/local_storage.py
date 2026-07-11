from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import UploadFile

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException


class LocalMaterialStorage:
    """课程资料本地文件存储。"""

    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _course_dir(self, course_id: UUID) -> Path:
        directory = self.root / "courses" / str(course_id)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    async def save_upload(
        self,
        *,
        course_id: UUID,
        material_id: UUID,
        extension: str,
        upload: UploadFile,
        max_bytes: int,
    ) -> tuple[str, int]:
        destination = self._course_dir(course_id) / f"{material_id}.{extension}"
        total = 0
        try:
            with destination.open("wb") as handle:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise BusinessException(
                            code=ErrorCode.PARAM_ERROR,
                            detail=f"文件大小不能超过 {max_bytes // (1024 * 1024)}MB",
                            status_code=400,
                        )
                    handle.write(chunk)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return str(destination), total

    def write_parsed_text(self, course_id: UUID, material_id: UUID, text: str) -> str:
        destination = self._course_dir(course_id) / f"{material_id}.parsed.txt"
        destination.write_text(text, encoding="utf-8")
        return str(destination)
