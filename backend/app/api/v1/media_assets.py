from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_student, require_student_bearer_or_query
from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.repositories.media_repository import MediaRepository
from app.schemas.multimodal import MediaAssetRead
from app.services.media_storage_service import MediaStorageService
from app.integrations.openmaic.client import OpenMAICClient
from app.core.config import settings
import time

router = APIRouter()


@router.get("/{asset_id}/launch")
async def launch_asset(
    asset_id: UUID,
    current_user: User = Depends(require_student_bearer_or_query),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    asset = await MediaRepository(db).get_asset_for_user(asset_id, current_user.id)
    if asset is None or asset.asset_type != "interactive_classroom":
        raise BusinessException(code=ErrorCode.NOT_FOUND, detail="沉浸课堂不存在", status_code=404)
    classroom_id = str((asset.render_meta or {}).get("classroom_id") or "")
    if not classroom_id:
        raise BusinessException(code=ErrorCode.NOT_FOUND, detail="沉浸课堂入口缺失", status_code=404)
    target = OpenMAICClient().build_signed_playback_url(
        classroom_id,
        expires_at_seconds=int(time.time()) + settings.openmaic_playback_token_ttl_seconds,
    )
    return RedirectResponse(target, status_code=307)


@router.get("/{asset_id}")
async def get_asset(
    asset_id: UUID,
    request: Request,
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    asset = await MediaRepository(db).get_asset_for_user(asset_id, current_user.id)
    if asset is None:
        raise BusinessException(code=ErrorCode.NOT_FOUND, detail="媒体资产不存在", status_code=404)
    data = MediaAssetRead.model_validate(asset).model_dump(mode="json")
    data["file_url"] = f"/api/v1/media-assets/{asset.id}/file"
    return success_response(data, request=request)


@router.get("/{asset_id}/file")
async def get_asset_file(
    asset_id: UUID,
    current_user: User = Depends(require_student_bearer_or_query),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    asset = await MediaRepository(db).get_asset_for_user(asset_id, current_user.id)
    if asset is None:
        raise BusinessException(code=ErrorCode.NOT_FOUND, detail="媒体资产不存在", status_code=404)
    path = MediaStorageService().resolve_owned_path(asset.storage_path)
    if not path.exists():
        raise BusinessException(code=ErrorCode.NOT_FOUND, detail="媒体文件不存在", status_code=404)
    return FileResponse(path, media_type=asset.mime_type, filename=path.name)
