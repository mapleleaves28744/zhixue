from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, RegisterRequest
from app.services.auth_service import AuthService


router = APIRouter()


@router.get("/ping")
async def ping(request: Request) -> dict[str, object]:
    return success_response({"module": "auth", "status": "ok"}, request=request)


@router.post("/register")
async def register(
    payload: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    user = await AuthService(db).register(payload)
    return success_response(user.model_dump(mode="json"), request=request)


@router.get("/check-username")
async def check_username(
    request: Request,
    username: str = Query(..., min_length=3, max_length=64),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    result = await AuthService(db).check_username(username)
    return success_response(result.model_dump(mode="json"), request=request)


@router.post("/login")
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    token = await AuthService(db).login(payload)
    return success_response(token.model_dump(mode="json"), request=request)


@router.post("/reset-password")
async def reset_password(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    user = await AuthService(db).reset_password()
    return success_response(user.model_dump(mode="json"), request=request)


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    user = await AuthService(db).change_password(current_user=current_user, payload=payload)
    return success_response(user.model_dump(mode="json"), request=request)
