from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db, require_role
from app.core.errors import NotFoundError
from app.models import AdminRole, AdminUser, SiteSettings
from app.schemas.admin import SiteSettingsRead, SiteSettingsUpdate

router = APIRouter(prefix="/admin/settings", tags=["admin:settings"])


@router.get("", response_model=SiteSettingsRead)
async def get_settings_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role(AdminRole.owner, AdminRole.staff))],
) -> SiteSettingsRead:
    settings = await db.get(SiteSettings, 1)
    if settings is None:
        raise NotFoundError("site settings not configured")
    return SiteSettingsRead.model_validate(settings)


@router.put("", response_model=SiteSettingsRead)
async def update_settings_endpoint(
    payload: SiteSettingsUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role(AdminRole.owner))],
) -> SiteSettingsRead:
    settings = await db.get(SiteSettings, 1)
    if settings is None:
        raise NotFoundError("site settings not configured")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    await db.flush()
    await db.refresh(settings)
    return SiteSettingsRead.model_validate(settings)
