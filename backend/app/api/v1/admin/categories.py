from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db, require_role
from app.models import AdminRole, AdminUser, Category
from app.schemas.admin import CategoryCreate, CategoryRead, CategoryUpdate
from app.services.admin_catalog import create_category, delete_category, update_category

router = APIRouter(prefix="/admin/categories", tags=["admin:catalog"])


@router.get("", response_model=list[CategoryRead])
async def list_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role(AdminRole.owner, AdminRole.staff))],
) -> list[CategoryRead]:
    result = await db.execute(select(Category).order_by(Category.display_order, Category.name))
    return [CategoryRead.model_validate(c) for c in result.scalars().all()]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CategoryRead)
async def create_category_endpoint(
    payload: CategoryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role(AdminRole.owner, AdminRole.staff))],
) -> CategoryRead:
    category = await create_category(db, payload)
    return CategoryRead.model_validate(category)


@router.put("/{category_id}", response_model=CategoryRead)
async def update_category_endpoint(
    category_id: int,
    payload: CategoryUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role(AdminRole.owner, AdminRole.staff))],
) -> CategoryRead:
    category = await update_category(db, category_id, payload)
    return CategoryRead.model_validate(category)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category_endpoint(
    category_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role(AdminRole.owner))],
) -> None:
    await delete_category(db, category_id)
