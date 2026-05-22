from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException


REFRESH_TOKEN_EXPIRE_DAYS = 7

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(
    user_id: UUID,
    username: str,
    role: str,
) -> tuple[str, int]:
    expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    expires_at = datetime.now(UTC) + expires_delta
    payload = _base_token_payload(user_id, username, role, "access", expires_at)
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int(expires_delta.total_seconds())


def create_refresh_token(user_id: UUID, username: str, role: str) -> str:
    expires_at = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = _base_token_payload(user_id, username, role, "refresh", expires_at)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except ExpiredSignatureError as exc:
        raise BusinessException(
            code=ErrorCode.TOKEN_EXPIRED,
            detail="Token 已过期",
            status_code=401,
        ) from exc
    except InvalidTokenError as exc:
        raise BusinessException(
            code=ErrorCode.UNAUTHORIZED,
            detail="Token 无效",
            status_code=401,
        ) from exc

    if payload.get("type") != expected_type or not payload.get("sub"):
        raise BusinessException(
            code=ErrorCode.UNAUTHORIZED,
            detail="Token 类型无效",
            status_code=401,
        )
    return payload


def _base_token_payload(
    user_id: UUID,
    username: str,
    role: str,
    token_type: str,
    expires_at: datetime,
) -> dict[str, Any]:
    return {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "type": token_type,
        "exp": expires_at,
        "iat": datetime.now(UTC),
    }
