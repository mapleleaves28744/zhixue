from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from uuid import uuid4

from app.core.config import settings


class MediaStorageService:
    def __init__(self) -> None:
        self.root = Path(settings.multimodal_storage_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, *, data: bytes, asset_type: str, suffix: str) -> tuple[str, int, str]:
        safe_suffix = suffix if suffix.startswith(".") else f".{suffix}"
        digest = hashlib.sha1(data).hexdigest()[:16]
        filename = f"{uuid4().hex}_{digest}{safe_suffix}"
        path = self.root / asset_type / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        mime_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        return str(path), len(data), mime_type

    def save_text(self, *, text: str, asset_type: str, suffix: str = ".html") -> tuple[str, int, str]:
        return self.save_bytes(data=text.encode("utf-8"), asset_type=asset_type, suffix=suffix)

    def resolve_owned_path(self, storage_path: str) -> Path:
        path = Path(storage_path).resolve()
        if self.root not in path.parents and path != self.root:
            raise RuntimeError("非法媒体路径")
        return path
