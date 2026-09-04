from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db, require_role
from app.models import AdminRole, AdminUser, DayOfWeek, Food
from app.schemas.admin import FoodAvailabilityUpdate, FoodCreate, FoodRead, FoodUpdate
from app.services.admin_catalog import (
    create_food,
    delete_food,
    set_food_availability,
    update_food,
)

router = APIRouter(prefix="/admin/foods", tags=["admin:catalog"])


@router.get("", response_model=list[FoodRead])
async def list_foods(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role(AdminRole.owner, AdminRole.staff))],
    category_id: Annotated[int | None, Query()] = None,
    available: Annotated[bool | None, Query()] = None,
    day_of_week: Annotated[DayOfWeek | None, Query()] = None,
) -> list[FoodRead]:
    stmt = select(Food).order_by(Food.name)
    if category_id is not None:
        stmt = stmt.where(Food.category_id == category_id)
    if available is not None:
        stmt = stmt.where(Food.is_available == available)
    if day_of_week is not None:
        stmt = stmt.where(Food.day_of_week == day_of_week)
    result = await db.execute(stmt)
    return [FoodRead.model_validate(f) for f in result.scalars().all()]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=FoodRead)
async def create_food_endpoint(
    payload: FoodCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role(AdminRole.owner, AdminRole.staff))],
) -> FoodRead:
    food = await create_food(db, payload)
    return FoodRead.model_validate(food)


@router.put("/{food_id}", response_model=FoodRead)
async def update_food_endpoint(
    food_id: int,
    payload: FoodUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role(AdminRole.owner, AdminRole.staff))],
) -> FoodRead:
    food = await update_food(db, food_id, payload)
    return FoodRead.model_validate(food)


@router.patch("/{food_id}/availability", response_model=FoodRead)
async def update_food_availability_endpoint(
    food_id: int,
    payload: FoodAvailabilityUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role(AdminRole.owner, AdminRole.staff))],
) -> FoodRead:
    food = await set_food_availability(db, food_id, payload.is_available)
    return FoodRead.model_validate(food)


@router.delete("/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_food_endpoint(
    food_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role(AdminRole.owner))],
) -> None:
    await delete_food(db, food_id)
