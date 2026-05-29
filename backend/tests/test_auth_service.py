from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import BusinessException
from app.core.security import hash_password, verify_password
from app.schemas.auth import ChangePasswordRequest, LoginRequest
from app.services.auth_service import AuthService


class _FakeDb:
    async def commit(self) -> None:
        return None

    async def refresh(self, obj: object) -> None:
        return None


class _FakeUsers:
    def __init__(self) -> None:
        self.user = SimpleNamespace(
            id=uuid4(),
            username="alice",
            email="alice@example.com",
            password_hash=hash_password("old-password"),
            role="student",
            status="active",
        )

    async def get_by_username(self, username: str):
        return self.user if username == self.user.username else None

    async def get_by_username_or_email(self, identifier: str):
        if identifier in {self.user.username, self.user.email}:
            return self.user
        return None

    async def set_last_login_now(self, user: object) -> None:
        return None


def _service(users: _FakeUsers) -> AuthService:
    service = AuthService.__new__(AuthService)
    service.db = _FakeDb()
    service.users = users
    return service


@pytest.mark.asyncio
async def test_login_accepts_email_identifier() -> None:
    users = _FakeUsers()
    token = await _service(users).login(
        LoginRequest(username="alice@example.com", password="old-password")
    )

    assert token.user.username == "alice"
    assert token.access_token


@pytest.mark.asyncio
async def test_check_username_reports_taken_name() -> None:
    result = await _service(_FakeUsers()).check_username("alice")

    assert result.available is False


@pytest.mark.asyncio
async def test_change_password_requires_current_password() -> None:
    users = _FakeUsers()

    with pytest.raises(BusinessException):
        await _service(users).change_password(
            current_user=users.user,
            payload=ChangePasswordRequest(
                current_password="wrong-password",
                new_password="new-password",
            ),
        )

    assert verify_password("old-password", users.user.password_hash)


@pytest.mark.asyncio
async def test_change_password_updates_hash_with_current_password() -> None:
    users = _FakeUsers()

    user = await _service(users).change_password(
        current_user=users.user,
        payload=ChangePasswordRequest(
            current_password="old-password",
            new_password="new-password",
        ),
    )

    assert user.username == "alice"
    assert verify_password("new-password", users.user.password_hash)


@pytest.mark.asyncio
async def test_reset_password_is_disabled() -> None:
    with pytest.raises(BusinessException):
        await _service(_FakeUsers()).reset_password()
