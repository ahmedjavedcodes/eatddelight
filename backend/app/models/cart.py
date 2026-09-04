from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.food import Food


class Cart(Base, TimestampMixin):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    items: Mapped[list[CartItem]] = relationship(
        back_populates="cart", cascade="all, delete-orphan", lazy="selectin"
    )


class CartItem(Base, TimestampMixin):
    __tablename__ = "cart_items"
    __table_args__ = (CheckConstraint("quantity >= 1", name="quantity_positive"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cart_id: Mapped[int] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id", ondelete="CASCADE"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(300))

    cart: Mapped[Cart] = relationship(back_populates="items")
    food: Mapped[Food] = relationship()
    addon_links: Mapped[list[CartItemAddon]] = relationship(
        back_populates="cart_item", cascade="all, delete-orphan", lazy="selectin"
    )


class CartItemAddon(Base):
    __tablename__ = "cart_item_addons"
    __table_args__ = (CheckConstraint("quantity >= 1", name="quantity_positive"),)

    cart_item_id: Mapped[int] = mapped_column(
        ForeignKey("cart_items.id", ondelete="CASCADE"), primary_key=True
    )
    addon_id: Mapped[int] = mapped_column(
        ForeignKey("addons.id", ondelete="CASCADE"), primary_key=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    cart_item: Mapped[CartItem] = relationship(back_populates="addon_links")
