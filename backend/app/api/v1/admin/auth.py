from typing import Annotated

import jwt
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db
from app.core.errors import AuthError
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models import AdminUser
from app.schemas.auth import AdminUserRead, LoginRequest, RefreshRequest, TokenPair
from app.services.auth import authenticate_admin, issue_tokens

router = APIRouter(prefix="/admin/auth", tags=["admin:auth"])


@router.post("/login", response_model=TokenPair)
async def login(
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair:
    user = await authenticate_admin(db, payload.email, payload.password)
    return issue_tokens(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair:
    try:
        data = decode_token(payload.refresh_token, expected_type="refresh")
    except jwt.PyJWTError as exc:
        raise AuthError("invalid or expired refresh token") from exc
    user = await db.get(AdminUser, int(data["sub"]))
    if user is None or not user.is_active:
        raise AuthError("account not found or inactive")
    return TokenPair(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id, user.role.value),
        user=AdminUserRead.model_validate(user),
    )
