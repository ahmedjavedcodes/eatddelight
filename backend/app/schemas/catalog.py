from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import DayOfWeek


class AddOnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: Decimal
    is_available: bool
    is_global: bool


class FoodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    name: str
    description: str | None
    price: Decimal
    image_url: str | None
    is_available: bool
    min_order_quantity: int
    is_single_serving: bool
    requires_advance_order: bool
    day_of_week: DayOfWeek | None


class FoodDetailRead(FoodRead):
    addons: list[AddOnRead]


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str | None
    display_order: int
    is_active: bool


class CategoryWithFoods(CategoryRead):
    foods: list[FoodRead]


class WeekdayGroup(BaseModel):
    day_of_week: DayOfWeek
    food: FoodRead
