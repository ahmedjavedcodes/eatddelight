from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db
from app.core.errors import NotFoundError
from app.models import Category, Food
from app.schemas.catalog import CategoryRead, FoodRead

router = APIRouter(prefix="/categories", tags=["catalog"])


@router.get("", response_model=list[CategoryRead])
async def list_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    exclude_weekly: Annotated[bool, Query()] = False,
) -> list[CategoryRead]:
    stmt = select(Category).where(Category.is_active.is_(True))
    if exclude_weekly:
        stmt = stmt.where(Category.slug != "menu-of-the-day")
    stmt = stmt.order_by(Category.display_order, Category.name)
    result = await db.execute(stmt)
    return [CategoryRead.model_validate(c) for c in result.scalars().all()]


@router.get("/{category_id}/foods", response_model=list[FoodRead])
async def list_category_foods(
    category_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    available: Annotated[bool | None, Query()] = None,
) -> list[FoodRead]:
    category = await db.get(Category, category_id)
    if category is None or not category.is_active:
        raise NotFoundError("category not found")
    stmt = select(Food).where(Food.category_id == category_id).order_by(Food.name)
    if available is not None:
        stmt = stmt.where(Food.is_available == available)
    result = await db.execute(stmt)
    return [FoodRead.model_validate(f) for f in result.scalars().all()]
