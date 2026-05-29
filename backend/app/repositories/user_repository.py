from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import StudentProfile
from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_username_or_email(self, identifier: str) -> User | None:
        result = await self.db.execute(
            select(User).where((User.username == identifier) | (User.email == identifier))
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        username: str,
        password_hash: str,
        email: str | None,
        role: str,
    ) -> User:
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role=role,
            status="active",
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def create_student_profile(self, user_id: UUID) -> StudentProfile:
        profile = StudentProfile(user_id=user_id)
        self.db.add(profile)
        await self.db.flush()
        return profile

    async def set_last_login_now(self, user: User) -> None:
        user.last_login_at = await self.db.scalar(select(func.now()))
        await self.db.flush()
