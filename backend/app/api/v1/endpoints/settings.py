from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db
from app.core.errors import NotFoundError
from app.models import SiteSettings
from app.schemas.settings import SiteSettingsRead

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SiteSettingsRead)
async def get_settings_endpoint(db: Annotated[AsyncSession, Depends(get_db)]) -> SiteSettingsRead:
    settings = await db.get(SiteSettings, 1)
    if settings is None:
        raise NotFoundError("site settings not configured")
    return SiteSettingsRead.model_validate(settings)
