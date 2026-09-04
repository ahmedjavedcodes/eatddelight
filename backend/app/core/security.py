"""Password hashing and admin JWT encode/decode.

Uses ``bcrypt`` directly: ``passlib`` 1.7.x is unmaintained and its bcrypt
backend self-test crashes against bcrypt >= 4.1 / 5.x.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import get_settings


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False


TokenType = Literal["access", "refresh"]


def _encode(sub: str, role: str, expires: timedelta, token_type: TokenType) -> str:
    settings = get_settings()
    now = datetime.now(tz=UTC)
    payload = {"sub": sub, "role": role, "type": token_type, "iat": now, "exp": now + expires}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int, role: str) -> str:
    settings = get_settings()
    return _encode(
        str(user_id), role, timedelta(minutes=settings.access_token_expire_minutes), "access"
    )


def create_refresh_token(user_id: int, role: str) -> str:
    settings = get_settings()
    return _encode(
        str(user_id), role, timedelta(days=settings.refresh_token_expire_days), "refresh"
    )


def decode_token(token: str, *, expected_type: TokenType) -> dict[str, Any]:
    settings = get_settings()
    data: dict[str, Any] = jwt.decode(
        token, settings.secret_key, algorithms=[settings.jwt_algorithm]
    )
    if data.get("type") != expected_type:
        raise jwt.InvalidTokenError("wrong token type")
    return data
