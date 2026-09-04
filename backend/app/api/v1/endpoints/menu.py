from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import get_db
from app.models import Category, DayOfWeek, Food
from app.schemas.catalog import CategoryWithFoods, FoodRead, WeekdayGroup

router = APIRouter(tags=["catalog"])

_WEEKDAY_ORDER = case(
    *[(Food.day_of_week == day, i) for i, day in enumerate(DayOfWeek)],
    else_=len(DayOfWeek),
)


@router.get("/menu", response_model=list[CategoryWithFoods])
async def get_menu(db: Annotated[AsyncSession, Depends(get_db)]) -> list[CategoryWithFoods]:
    stmt = (
        select(Category)
        .where(Category.is_active.is_(True), Category.slug != "menu-of-the-day")
        .options(selectinload(Category.foods))
        .order_by(Category.display_order, Category.name)
    )
    categories = (await db.execute(stmt)).scalars().all()
    return [CategoryWithFoods.model_validate(c) for c in categories if c.foods]


@router.get("/weekly-menu", response_model=list[WeekdayGroup])
async def get_weekly_menu(db: Annotated[AsyncSession, Depends(get_db)]) -> list[WeekdayGroup]:
    stmt = select(Food).where(Food.day_of_week.is_not(None)).order_by(_WEEKDAY_ORDER, Food.id)
    foods = (await db.execute(stmt)).scalars().all()
    seen: set[DayOfWeek] = set()
    groups: list[WeekdayGroup] = []
    for food in foods:
        assert food.day_of_week is not None
        if food.day_of_week in seen:
            continue
        seen.add(food.day_of_week)
        groups.append(
            WeekdayGroup(day_of_week=food.day_of_week, food=FoodRead.model_validate(food))
        )
    return groups
