from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import EmailConflictError, LastOwnerError, NotFoundError
from app.core.security import hash_password
from app.models import AdminRole, AdminUser
from app.schemas.admin import StaffCreate, StaffUpdate


async def create_staff(session: AsyncSession, payload: StaffCreate) -> AdminUser:
    email = payload.email.lower().strip()
    existing = await session.execute(select(AdminUser).where(AdminUser.email == email))
    if existing.scalar_one_or_none() is not None:
        raise EmailConflictError(f"an account with email '{email}' already exists")
    staff = AdminUser(
        name=payload.name,
        email=email,
        hashed_password=hash_password(payload.password),
        role=AdminRole.staff,
        is_active=True,
    )
    session.add(staff)
    await session.flush()
    return staff


async def get_admin_user_or_404(session: AsyncSession, user_id: int) -> AdminUser:
    user = await session.get(AdminUser, user_id)
    if user is None:
        raise NotFoundError("admin user not found")
    return user


async def _active_owner_count(session: AsyncSession, *, exclude_id: int | None = None) -> int:
    stmt = (
        select(func.count())
        .select_from(AdminUser)
        .where(AdminUser.role == AdminRole.owner, AdminUser.is_active.is_(True))
    )
    if exclude_id is not None:
        stmt = stmt.where(AdminUser.id != exclude_id)
    return int(await session.scalar(stmt) or 0)


async def update_staff(session: AsyncSession, user_id: int, payload: StaffUpdate) -> AdminUser:
    user = await get_admin_user_or_404(session, user_id)
    if (
        payload.is_active is False
        and user.role == AdminRole.owner
        and await _active_owner_count(session, exclude_id=user.id) == 0
    ):
        raise LastOwnerError("cannot deactivate the last active owner")
    if payload.name is not None:
        user.name = payload.name
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password is not None:
        user.hashed_password = hash_password(payload.password)
    await session.flush()
    return user
