from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import AdminRole, DayOfWeek, OrderSource, OrderStatus
from app.schemas.catalog import AddOnRead, CategoryRead, FoodRead

# --- Category ---


class CategoryCreate(BaseModel):
    name: Annotated[str, Field(max_length=120)]
    description: Annotated[str, Field(max_length=500)] | None = None
    display_order: int = 0
    is_active: bool = True


class CategoryUpdate(BaseModel):
    name: Annotated[str, Field(max_length=120)] | None = None
    description: Annotated[str, Field(max_length=500)] | None = None
    display_order: int | None = None
    is_active: bool | None = None
    regenerate_slug: bool = False


# --- Food ---


class FoodVariantIn(BaseModel):
    label: Annotated[str, Field(max_length=60, min_length=1)]
    price: Annotated[Decimal, Field(gt=0)]


def _check_variants_distinct(variants: list[FoodVariantIn] | None) -> None:
    if not variants:
        return
    labels = [v.label.strip().lower() for v in variants]
    if len(labels) != len(set(labels)):
        raise ValueError("variant labels must be unique for a product")
    prices = [v.price for v in variants]
    if len(prices) != len(set(prices)):
        raise ValueError("variant prices must be different from each other")


class FoodCreate(BaseModel):
    category_id: int
    name: Annotated[str, Field(max_length=160)]
    description: Annotated[str, Field(max_length=1000)] | None = None
    price: Annotated[Decimal, Field(gt=0)]
    image_url: Annotated[str, Field(max_length=500)] | None = None
    is_available: bool = True
    min_order_quantity: Annotated[int, Field(ge=1)] = 1
    is_single_serving: bool = True
    requires_advance_order: bool = True
    day_of_week: DayOfWeek | None = None
    variants: list[FoodVariantIn] | None = None

    @model_validator(mode="after")
    def _validate_variants(self) -> Self:
        _check_variants_distinct(self.variants)
        return self


class FoodUpdate(BaseModel):
    category_id: int | None = None
    name: Annotated[str, Field(max_length=160)] | None = None
    description: Annotated[str, Field(max_length=1000)] | None = None
    price: Annotated[Decimal, Field(gt=0)] | None = None
    image_url: Annotated[str, Field(max_length=500)] | None = None
    is_available: bool | None = None
    min_order_quantity: Annotated[int, Field(ge=1)] | None = None
    is_single_serving: bool | None = None
    requires_advance_order: bool | None = None
    day_of_week: DayOfWeek | None = None
    variants: list[FoodVariantIn] | None = None

    @model_validator(mode="after")
    def _validate_variants(self) -> Self:
        _check_variants_distinct(self.variants)
        return self


class FoodAvailabilityUpdate(BaseModel):
    is_available: bool


# --- AddOn ---


class AddOnCreate(BaseModel):
    name: Annotated[str, Field(max_length=120)]
    price: Annotated[Decimal, Field(ge=0)]
    is_available: bool = True
    is_global: bool = False
    food_ids: list[int] = Field(default_factory=list)


class AddOnUpdate(BaseModel):
    name: Annotated[str, Field(max_length=120)] | None = None
    price: Annotated[Decimal, Field(ge=0)] | None = None
    is_available: bool | None = None
    is_global: bool | None = None
    food_ids: list[int] | None = None


# --- Orders (admin) ---


class OrderItemAddonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    addon_id: int | None
    addon_name: str
    quantity: int
    unit_price: Decimal


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    food_id: int | None
    food_name: str
    quantity: int
    unit_price: Decimal
    notes: str | None
    addon_links: list[OrderItemAddonRead]


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_number: str
    customer_name: str
    customer_phone: str
    order_source: OrderSource
    requested_date: date
    status: OrderStatus
    subtotal: Decimal | None
    total: Decimal | None
    is_custom: bool
    custom_description: str | None
    admin_notes: str | None
    servings: int | None
    budget_range: str | None
    occasion: str | None
    event_date: date | None
    created_at: datetime
    items: list[OrderItemRead]


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    admin_notes: str | None = None


class OrderQuoteUpdate(BaseModel):
    subtotal: Decimal | None = None
    total: Annotated[Decimal, Field(ge=0)]


# --- Staff ---


class StaffCreate(BaseModel):
    name: Annotated[str, Field(max_length=120)]
    email: Annotated[str, Field(max_length=255)]
    password: Annotated[str, Field(min_length=8)]


class StaffUpdate(BaseModel):
    name: Annotated[str, Field(max_length=120)] | None = None
    is_active: bool | None = None
    password: Annotated[str, Field(min_length=8)] | None = None


class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: AdminRole
    is_active: bool
    created_at: datetime


# --- Site settings ---


class SiteSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    business_name: str
    tagline: str | None
    about_text: str | None
    contact_phone: str
    whatsapp_number: str
    instagram_handle: str
    address: str | None
    opening_hours: str | None
    updated_at: datetime


class SiteSettingsUpdate(BaseModel):
    business_name: Annotated[str, Field(max_length=120)] | None = None
    tagline: Annotated[str, Field(max_length=200)] | None = None
    about_text: str | None = None
    contact_phone: Annotated[str, Field(max_length=32)] | None = None
    whatsapp_number: Annotated[str, Field(max_length=20)] | None = None
    instagram_handle: Annotated[str, Field(max_length=60)] | None = None
    address: Annotated[str, Field(max_length=300)] | None = None
    opening_hours: Annotated[str, Field(max_length=300)] | None = None


# --- Uploads ---


class ImageUploadRead(BaseModel):
    url: str


__all__ = [
    "AddOnCreate",
    "AddOnRead",
    "AddOnUpdate",
    "AdminUserRead",
    "CategoryCreate",
    "CategoryRead",
    "CategoryUpdate",
    "FoodAvailabilityUpdate",
    "FoodCreate",
    "FoodRead",
    "FoodUpdate",
    "FoodVariantIn",
    "ImageUploadRead",
    "OrderItemAddonRead",
    "OrderItemRead",
    "OrderQuoteUpdate",
    "OrderRead",
    "OrderStatusUpdate",
    "SiteSettingsRead",
    "SiteSettingsUpdate",
    "StaffCreate",
    "StaffUpdate",
]
