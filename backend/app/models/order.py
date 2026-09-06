from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import OrderSource, OrderStatus


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("invoice_number", name="uq_orders_invoice_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(24), nullable=False)
    lookup_token: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    order_source: Mapped[OrderSource] = mapped_column(
        SAEnum(OrderSource, name="order_source"), nullable=False
    )
    requested_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus, name="order_status"),
        default=OrderStatus.pending,
        server_default=text("'pending'"),
        nullable=False,
    )
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    total: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    is_custom: Mapped[bool] = mapped_column(
        default=False, server_default=text("false"), nullable=False
    )
    custom_description: Mapped[str | None] = mapped_column(Text)
    admin_notes: Mapped[str | None] = mapped_column(Text)
    whatsapp_link_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Structured custom-order fields (all optional; see spec 02 FR5).
    servings: Mapped[int | None] = mapped_column(Integer)
    budget_range: Mapped[str | None] = mapped_column(String(60))
    occasion: Mapped[str | None] = mapped_column(String(120))
    event_date: Mapped[date | None] = mapped_column(Date)

    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (CheckConstraint("quantity >= 1", name="quantity_positive"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False
    )
    food_id: Mapped[int | None] = mapped_column(ForeignKey("foods.id", ondelete="SET NULL"))
    food_name: Mapped[str] = mapped_column(String(160), nullable=False)
    variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("food_variants.id", ondelete="SET NULL")
    )
    variant_label: Mapped[str | None] = mapped_column(String(60))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(300))

    order: Mapped[Order] = relationship(back_populates="items")
    addon_links: Mapped[list[OrderItemAddon]] = relationship(
        back_populates="order_item", cascade="all, delete-orphan", lazy="selectin"
    )


class OrderItemAddon(Base):
    __tablename__ = "order_item_addons"
    __table_args__ = (
        UniqueConstraint("order_item_id", "addon_id", name="uq_order_item_addons_item_addon"),
        CheckConstraint("quantity >= 1", name="quantity_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_item_id: Mapped[int] = mapped_column(
        ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False
    )
    addon_id: Mapped[int | None] = mapped_column(ForeignKey("addons.id", ondelete="SET NULL"))
    addon_name: Mapped[str] = mapped_column(String(120), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)

    order_item: Mapped[OrderItem] = relationship(back_populates="addon_links")
