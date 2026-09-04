from collections.abc import Callable, Coroutine
from typing import Annotated

import jwt
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthError, ForbiddenError
from app.core.security import decode_token
from app.db.session import get_db
from app.models import AdminRole, AdminUser

__all__ = [
    "get_current_admin_user",
    "get_db",
    "get_session_token",
    "require_role",
]


async def get_session_token(
    x_session_token: Annotated[str, Header(min_length=1)],
) -> str:
    """The anonymous customer's opaque bucket key. Presence-checked only."""
    return x_session_token


bearer = HTTPBearer(auto_error=False)


async def get_current_admin_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUser:
    if creds is None:
        raise AuthError("missing bearer token")
    try:
        data = decode_token(creds.credentials, expected_type="access")
    except jwt.PyJWTError as exc:
        raise AuthError("invalid or expired token") from exc
    user = await db.get(AdminUser, int(data["sub"]))
    if user is None or not user.is_active:
        raise AuthError("account not found or inactive")
    return user


def require_role(
    *roles: AdminRole,
) -> Callable[[AdminUser], Coroutine[None, None, AdminUser]]:
    async def _dep(
        user: Annotated[AdminUser, Depends(get_current_admin_user)],
    ) -> AdminUser:
        if user.role not in roles:
            raise ForbiddenError(f"requires role: {', '.join(r.value for r in roles)}")
        return user

    return _dep
