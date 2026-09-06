from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.food import Food


class FoodVariant(Base, TimestampMixin):
    """An optional named size/quantity option for a Food, each with its own price.

    e.g. Chicken Karahi: "500g" -> 800, "1kg" -> 2000, "2kg" -> 3000. A Food with
    no variants is ordered at its own ``price``; a Food with variants is always
    ordered by picking one of these instead.
    """

    __tablename__ = "food_variants"
    __table_args__ = (
        CheckConstraint("price > 0", name="price_positive"),
        UniqueConstraint("food_id", "label", name="uq_food_variants_food_id_label"),
        UniqueConstraint("food_id", "price", name="uq_food_variants_food_id_price"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    food_id: Mapped[int] = mapped_column(
        ForeignKey("foods.id", ondelete="CASCADE"), index=True, nullable=False
    )
    label: Mapped[str] = mapped_column(String(60), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))

    food: Mapped[Food] = relationship(back_populates="variants")
