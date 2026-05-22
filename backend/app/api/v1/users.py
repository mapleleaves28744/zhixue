from fastapi import APIRouter, Depends, Request

from app.core.deps import get_current_user
from app.core.response import success_response
from app.models.user import User
from app.schemas.user import UserRead


router = APIRouter()


@router.get("/ping")
async def ping(request: Request) -> dict[str, object]:
    return success_response({"module": "users", "status": "ok"}, request=request)


@router.get("/me")
async def read_me(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    user = UserRead.model_validate(current_user)
    return success_response(user.model_dump(mode="json"), request=request)
