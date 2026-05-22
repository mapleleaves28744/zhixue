from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise BusinessException(
            code=ErrorCode.UNAUTHORIZED,
            detail="缺少 Bearer Token",
            status_code=401,
        )

    payload = decode_token(credentials.credentials, expected_type="access")
    try:
        user_id = UUID(str(payload["sub"]))
    except (KeyError, ValueError) as exc:
        raise BusinessException(
            code=ErrorCode.UNAUTHORIZED,
            detail="Token 用户 ID 无效",
            status_code=401,
        ) from exc

    user = await UserRepository(db).get_by_id(user_id)
    if user is None:
        raise BusinessException(
            code=ErrorCode.NOT_FOUND,
            detail="用户不存在",
            status_code=404,
        )
    if user.status != "active":
        raise BusinessException(
            code=ErrorCode.FORBIDDEN,
            detail="用户已被禁用",
            status_code=403,
        )
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise BusinessException(
            code=ErrorCode.FORBIDDEN,
            detail="需要管理员权限",
            status_code=403,
        )
    return current_user


async def require_student(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "student":
        raise BusinessException(
            code=ErrorCode.FORBIDDEN,
            detail="需要学生权限",
            status_code=403,
        )
    return current_user
