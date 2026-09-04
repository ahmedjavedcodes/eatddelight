from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class AddOn(Base, TimestampMixin):
    __tablename__ = "addons"
    __table_args__ = (CheckConstraint("price >= 0", name="price_nonneg"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    is_available: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    is_global: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
