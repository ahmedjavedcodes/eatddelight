from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db, require_role
from app.models import AddOn, AdminRole, AdminUser
from app.schemas.admin import AddOnCreate, AddOnRead, AddOnUpdate
from app.services.admin_catalog import create_addon, delete_addon, update_addon

router = APIRouter(prefix="/admin/addons", tags=["admin:catalog"])


@router.get("", response_model=list[AddOnRead])
async def list_addons(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role(AdminRole.owner, AdminRole.staff))],
) -> list[AddOnRead]:
    result = await db.execute(select(AddOn).order_by(AddOn.name))
    return [AddOnRead.model_validate(a) for a in result.scalars().all()]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AddOnRead)
async def create_addon_endpoint(
    payload: AddOnCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role(AdminRole.owner, AdminRole.staff))],
) -> AddOnRead:
    addon = await create_addon(db, payload)
    return AddOnRead.model_validate(addon)


@router.put("/{addon_id}", response_model=AddOnRead)
async def update_addon_endpoint(
    addon_id: int,
    payload: AddOnUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role(AdminRole.owner, AdminRole.staff))],
) -> AddOnRead:
    addon = await update_addon(db, addon_id, payload)
    return AddOnRead.model_validate(addon)


@router.delete("/{addon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_addon_endpoint(
    addon_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role(AdminRole.owner))],
) -> None:
    await delete_addon(db, addon_id)
