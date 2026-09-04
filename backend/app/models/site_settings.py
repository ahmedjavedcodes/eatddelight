from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SiteSettings(Base):
    __tablename__ = "site_settings"
    __table_args__ = (CheckConstraint("id = 1", name="singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    business_name: Mapped[str] = mapped_column(String(120), nullable=False)
    tagline: Mapped[str | None] = mapped_column(String(200))
    about_text: Mapped[str | None] = mapped_column(Text)
    contact_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    whatsapp_number: Mapped[str] = mapped_column(String(20), nullable=False)
    instagram_handle: Mapped[str] = mapped_column(String(60), nullable=False)
    address: Mapped[str | None] = mapped_column(String(300))
    opening_hours: Mapped[str | None] = mapped_column(String(300))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
