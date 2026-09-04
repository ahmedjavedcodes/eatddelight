from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db, require_role
from app.models import AdminRole, AdminUser
from app.schemas.admin import AdminUserRead, StaffCreate, StaffUpdate
from app.services.staff import create_staff, update_staff

router = APIRouter(
    prefix="/admin/staff",
    tags=["admin:staff"],
    dependencies=[Depends(require_role(AdminRole.owner))],
)


@router.get("", response_model=list[AdminUserRead])
async def list_staff(db: Annotated[AsyncSession, Depends(get_db)]) -> list[AdminUserRead]:
    result = await db.execute(select(AdminUser).order_by(AdminUser.name))
    return [AdminUserRead.model_validate(u) for u in result.scalars().all()]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AdminUserRead)
async def create_staff_endpoint(
    payload: StaffCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserRead:
    staff = await create_staff(db, payload)
    return AdminUserRead.model_validate(staff)


@router.patch("/{user_id}", response_model=AdminUserRead)
async def update_staff_endpoint(
    user_id: int,
    payload: StaffUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserRead:
    user = await update_staff(db, user_id, payload)
    return AdminUserRead.model_validate(user)
