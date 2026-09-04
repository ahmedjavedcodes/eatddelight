"""Idempotent seed of the Daughter's Delight catalog (CLAUDE.md section 5).

Loads SiteSettings (id=1), one owner AdminUser (from OWNER_* env, only if none
exists), 11 categories and 42 foods. Re-running upserts: mutable fields
(price, min-order-qty, single-serving / advance-order flags) are refreshed to the
seed values; the owner password and admin-set About/Contact copy are never
touched. No AddOn rows are seeded.

Run:  python -m scripts.seed_menu   (after `alembic upgrade head`)
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import AdminRole, AdminUser, Category, DayOfWeek, Food, SiteSettings

# (day_of_week, name, price) — one dish per weekday, single-serving, min qty 1.
MENU_OF_THE_DAY: list[tuple[DayOfWeek, str, str]] = [
    (DayOfWeek.mon, "Makhni Handi with Salad+Roti", "600"),
    (DayOfWeek.tue, "Chicken Spicy Mandi with Sauces", "600"),
    (DayOfWeek.wed, "Special Khauasay with Curry", "550"),
    (DayOfWeek.thu, "Alfredo Pasta with Sauce", "600"),
    (DayOfWeek.fri, "Chicken Biryani with Raita + Salad", "500"),
]

# (slug, display name, [(dish name, price), ...]) — all min qty 3, no day_of_week.
FULL_MENU: list[tuple[str, str, list[tuple[str, str]]]] = [
    (
        "rice",
        "Rice",
        [
            ("Chicken Biryani", "400"),
            ("Spicy Mandi", "600"),
            ("Peas Pulao", "300"),
            ("Fried Rice", "400"),
            ("Beef Biryani", "480"),
        ],
    ),
    (
        "gravy",
        "Gravy",
        [
            ("Boneless Makhni Handi", "600"),
            ("Chicken Haleem", "380"),
            ("Chicken Achari", "350"),
            ("Seekh Kabab Handi", "550"),
            ("Chicken Kofta", "350"),
            ("Desi Dam Qeema", "450"),
            ("Chicken Nihari", "480"),
        ],
    ),
    (
        "meat-y",
        "Meat-y",
        [
            ("Alo Goshat", "380"),
            ("Seekh Kabab", "300"),
            ("Beef Handi", "600"),
        ],
    ),
    (
        "dal-with-tarka",
        "Dal with Tarka",
        [
            ("Dal Chana with Tarka", "250"),
            ("Makhni Dal", "300"),
            ("Dal Chawal", "300"),
            ("Dal Mong Special", "250"),
            ("Dal Mash with Spice", "300"),
        ],
    ),
    (
        "chinese",
        "Chinese",
        [
            ("Shashlik with Rice", "650"),
            ("Jalfrezi with Rice", "650"),
        ],
    ),
    (
        "khousay",
        "Khousay",
        [
            ("Special Khousay", "550"),
            ("Curry Pakora", "250"),
        ],
    ),
    (
        "fit-and-healthy",
        "Fit and Healthy",
        [
            ("Russian Salad", "350"),
            ("Ceasar Salad", "480"),
            ("Asian Salad", "350"),
            ("Hummus with Bread", "600"),
        ],
    ),
    (
        "desi-vegetarian",
        "Desi Vegetarian",
        [
            ("Sizler Bhindi", "280"),
            ("Mix Sabzi", "250"),
            ("Alo Palak", "250"),
        ],
    ),
    (
        "house-favourites",
        "House Favourites",
        [
            ("Alfredo Pasta", "550"),
            ("Chicken Raps", "380"),
        ],
    ),
    (
        "sweet-snack",
        "Sweet Snack",
        [
            ("Brownies", "280"),
            ("Special Kheer", "300"),
            ("Zarda", "250"),
            ("Kunafa", "900"),
        ],
    ),
]

SITE_SETTINGS: dict[str, str] = {
    "business_name": "Daughter's Delight",
    "tagline": "Homemade Made with Love",
    "contact_phone": "0312-2252915",
    "whatsapp_number": "923122252915",
    "instagram_handle": "eatddelight",
}


async def _upsert_category(
    session: AsyncSession, slug: str, name: str, display_order: int
) -> Category:
    result = await session.execute(select(Category).where(Category.slug == slug))
    category = result.scalar_one_or_none()
    if category is None:
        category = Category(slug=slug, name=name, display_order=display_order, is_active=True)
        session.add(category)
        await session.flush()
    else:
        category.name = name
        category.display_order = display_order
        category.is_active = True
    return category


async def _upsert_food(
    session: AsyncSession,
    category: Category,
    name: str,
    price: Decimal,
    *,
    day_of_week: DayOfWeek | None,
    min_order_quantity: int,
) -> Food:
    stmt = select(Food).where(Food.category_id == category.id, Food.name == name)
    if day_of_week is None:
        stmt = stmt.where(Food.day_of_week.is_(None))
    else:
        stmt = stmt.where(Food.day_of_week == day_of_week)

    food = (await session.execute(stmt)).scalar_one_or_none()
    if food is None:
        food = Food(
            category_id=category.id,
            name=name,
            price=price,
            day_of_week=day_of_week,
            min_order_quantity=min_order_quantity,
            is_single_serving=True,
            requires_advance_order=True,
            is_available=True,
        )
        session.add(food)
        await session.flush()
    else:
        food.price = price
        food.min_order_quantity = min_order_quantity
        food.is_single_serving = True
        food.requires_advance_order = True
    return food


async def _seed_site_settings(session: AsyncSession) -> None:
    row = await session.get(SiteSettings, 1)
    if row is None:
        session.add(SiteSettings(id=1, **SITE_SETTINGS))
    else:
        for key, value in SITE_SETTINGS.items():
            setattr(row, key, value)


async def _ensure_owner(session: AsyncSession) -> None:
    result = await session.execute(
        select(AdminUser).where(AdminUser.role == AdminRole.owner).limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return
    settings = get_settings()
    session.add(
        AdminUser(
            name=settings.owner_name,
            email=settings.owner_email.lower(),
            hashed_password=hash_password(settings.owner_password),
            role=AdminRole.owner,
            is_active=True,
        )
    )


async def seed(session: AsyncSession) -> None:
    await _seed_site_settings(session)
    await _ensure_owner(session)

    daily = await _upsert_category(session, "menu-of-the-day", "Menu of the Day", 0)
    for day_of_week, name, price in MENU_OF_THE_DAY:
        await _upsert_food(
            session,
            daily,
            name,
            Decimal(price),
            day_of_week=day_of_week,
            min_order_quantity=1,
        )

    for display_order, (slug, name, dishes) in enumerate(FULL_MENU, start=1):
        category = await _upsert_category(session, slug, name, display_order)
        for dish_name, price in dishes:
            await _upsert_food(
                session,
                category,
                dish_name,
                Decimal(price),
                day_of_week=None,
                min_order_quantity=3,
            )

    await session.commit()


async def _run() -> None:
    async with SessionLocal() as session:
        await seed(session)


if __name__ == "__main__":
    asyncio.run(_run())
