from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import DayOfWeek

if TYPE_CHECKING:
    from app.models.addon import AddOn
    from app.models.category import Category
    from app.models.food_variant import FoodVariant

food_addons = Table(
    "food_addons",
    Base.metadata,
    Column("food_id", ForeignKey("foods.id", ondelete="CASCADE"), primary_key=True),
    Column("addon_id", ForeignKey("addons.id", ondelete="CASCADE"), primary_key=True),
)


class Food(Base, TimestampMixin):
    __tablename__ = "foods"
    __table_args__ = (
        CheckConstraint("price > 0", name="price_positive"),
        CheckConstraint("min_order_quantity >= 1", name="min_qty"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000))
    price: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500))
    is_available: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    min_order_quantity: Mapped[int] = mapped_column(
        Integer, default=1, server_default=text("1"), nullable=False
    )
    is_single_serving: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    requires_advance_order: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    day_of_week: Mapped[DayOfWeek | None] = mapped_column(
        SAEnum(DayOfWeek, name="day_of_week"), index=True
    )

    category: Mapped[Category] = relationship(back_populates="foods")
    addons: Mapped[list[AddOn]] = relationship(secondary=food_addons, lazy="selectin")
    variants: Mapped[list[FoodVariant]] = relationship(
        back_populates="food",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="FoodVariant.display_order",
    )
