from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthError
from app.core.security import create_access_token, create_refresh_token, verify_password
from app.models import AdminUser
from app.schemas.auth import AdminUserRead, TokenPair


async def authenticate_admin(session: AsyncSession, email: str, password: str) -> AdminUser:
    result = await session.execute(
        select(AdminUser).where(AdminUser.email == email.lower().strip())
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(password, user.hashed_password):
        raise AuthError("invalid email or password")
    return user


def issue_tokens(user: AdminUser) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id, user.role.value),
        user=AdminUserRead.model_validate(user),
    )
