from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthUser, LoginRequest, RegisterRequest, TokenResponse


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)

    async def register(self, payload: RegisterRequest) -> AuthUser:
        username = payload.username.strip()
        email = payload.email.strip() if payload.email else None
        role = payload.role.strip() if payload.role else "student"

        if role != "student":
            raise BusinessException(
                code=ErrorCode.FORBIDDEN,
                detail="公开注册只允许创建 student 用户",
                status_code=403,
            )

        if await self.users.get_by_username(username):
            raise BusinessException(
                code=ErrorCode.CONFLICT,
                detail="用户名已存在",
                status_code=409,
            )

        if email and await self.users.get_by_email(email):
            raise BusinessException(
                code=ErrorCode.CONFLICT,
                detail="邮箱已存在",
                status_code=409,
            )

        user = await self.users.create_user(
            username=username,
            email=email,
            password_hash=hash_password(payload.password),
            role=role,
        )
        await self.users.create_student_profile(user.id)
        await self.db.commit()
        await self.db.refresh(user)
        return AuthUser.model_validate(user)

    async def login(self, payload: LoginRequest) -> TokenResponse:
        user = await self.users.get_by_username(payload.username.strip())
        if user is None or not verify_password(payload.password, user.password_hash):
            raise BusinessException(
                code=ErrorCode.UNAUTHORIZED,
                detail="用户名或密码错误",
                status_code=401,
            )

        if user.status != "active":
            raise BusinessException(
                code=ErrorCode.FORBIDDEN,
                detail="用户已被禁用",
                status_code=403,
            )

        access_token, expires_in = create_access_token(
            user_id=user.id,
            username=user.username,
            role=user.role,
        )
        refresh_token = create_refresh_token(
            user_id=user.id,
            username=user.username,
            role=user.role,
        )
        await self.users.set_last_login_now(user)
        await self.db.commit()
        await self.db.refresh(user)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            user=AuthUser.model_validate(user),
        )
