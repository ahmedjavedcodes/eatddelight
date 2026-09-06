from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db
from app.core.errors import NotFoundError
from app.models import DayOfWeek, Food
from app.schemas.catalog import AddOnRead, FoodDetailRead, FoodRead
from app.services.catalog import resolve_addons_for_food

router = APIRouter(prefix="/foods", tags=["catalog"])


@router.get("", response_model=list[FoodRead])
async def list_foods(
    db: Annotated[AsyncSession, Depends(get_db)],
    search: Annotated[str | None, Query()] = None,
    category_id: Annotated[int | None, Query()] = None,
    day_of_week: Annotated[DayOfWeek | None, Query()] = None,
    available: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(le=200, ge=1)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[FoodRead]:
    stmt = select(Food).order_by(Food.name).limit(limit).offset(offset)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(or_(Food.name.ilike(pattern), Food.description.ilike(pattern)))
    if category_id is not None:
        stmt = stmt.where(Food.category_id == category_id)
    if day_of_week is not None:
        stmt = stmt.where(Food.day_of_week == day_of_week)
    if available is not None:
        stmt = stmt.where(Food.is_available == available)
    result = await db.execute(stmt)
    return [FoodRead.model_validate(f) for f in result.scalars().all()]


@router.get("/{food_id}", response_model=FoodDetailRead)
async def get_food(
    food_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FoodDetailRead:
    food = await db.get(Food, food_id)
    if food is None:
        raise NotFoundError("food not found")
    await db.refresh(food, attribute_names=["variants"])
    addons = await resolve_addons_for_food(db, food)
    return FoodDetailRead(
        **FoodRead.model_validate(food).model_dump(),
        addons=[AddOnRead.model_validate(a) for a in addons],
    )
