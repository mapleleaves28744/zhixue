from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success_response
from app.db.session import get_db
from app.schemas.auth import LoginRequest, RegisterRequest
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


@router.post("/login")
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    token = await AuthService(db).login(payload)
    return success_response(token.model_dump(mode="json"), request=request)
