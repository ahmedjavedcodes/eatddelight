from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile

from app.api.v1.deps import require_role
from app.models import AdminRole, AdminUser
from app.schemas.admin import ImageUploadRead
from app.services.uploads import save_image_upload

router = APIRouter(prefix="/admin/uploads", tags=["admin:uploads"])


@router.post("/image", response_model=ImageUploadRead)
async def upload_image(
    file: UploadFile,
    _: Annotated[AdminUser, Depends(require_role(AdminRole.owner, AdminRole.staff))],
) -> ImageUploadRead:
    url = await save_image_upload(file)
    return ImageUploadRead(url=url)
