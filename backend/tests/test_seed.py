from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import verify_password
from app.models import AddOn, AdminRole, AdminUser, Category, DayOfWeek, Food, SiteSettings
from scripts.seed_menu import seed


async def _counts(session) -> dict[str, int]:
    async def count(stmt) -> int:
        return int(await session.scalar(stmt) or 0)

    return {
        "categories": await count(select(func.count()).select_from(Category)),
        "foods": await count(select(func.count()).select_from(Food)),
        "daily": await count(
            select(func.count()).select_from(Food).where(Food.day_of_week.is_not(None))
        ),
        "site_settings": await count(select(func.count()).select_from(SiteSettings)),
        "owners": await count(
            select(func.count()).select_from(AdminUser).where(AdminUser.role == AdminRole.owner)
        ),
        "addons": await count(select(func.count()).select_from(AddOn)),
    }


async def test_seed_fresh_counts(db_session):
    await seed(db_session)
    counts = await _counts(db_session)
    assert counts["categories"] == 11
    assert counts["foods"] == 42
    assert counts["daily"] == 5
    assert counts["foods"] - counts["daily"] == 37
    assert counts["site_settings"] == 1
    assert counts["owners"] == 1
    assert counts["addons"] == 0


async def test_seed_is_idempotent(db_session):
    await seed(db_session)
    first = await _counts(db_session)
    await seed(db_session)
    second = await _counts(db_session)
    assert first == second


async def test_seed_resets_hand_edited_price(db_session):
    await seed(db_session)
    biryani = await db_session.scalar(
        select(Food).join(Category).where(Category.slug == "rice", Food.name == "Chicken Biryani")
    )
    assert biryani is not None
    biryani.price = Decimal("1.00")
    await db_session.flush()

    await seed(db_session)
    await db_session.refresh(biryani)
    assert biryani.price == Decimal("400.00")


async def test_seed_does_not_create_second_owner_or_rotate_password(db_session):
    await seed(db_session)
    owner = await db_session.scalar(select(AdminUser).where(AdminUser.role == AdminRole.owner))
    assert owner is not None
    original_hash = owner.hashed_password

    await seed(db_session)
    owners = await db_session.scalar(
        select(func.count()).select_from(AdminUser).where(AdminUser.role == AdminRole.owner)
    )
    await db_session.refresh(owner)
    assert owners == 1
    assert owner.hashed_password == original_hash
    assert verify_password(get_settings().owner_password, owner.hashed_password)


async def test_seed_keeps_deliberate_duplicate_dishes_separate(db_session):
    await seed(db_session)

    thursday_alfredo = await db_session.scalar(
        select(Food).where(Food.name == "Alfredo Pasta with Sauce")
    )
    house_alfredo = await db_session.scalar(
        select(Food)
        .join(Category)
        .where(Category.slug == "house-favourites", Food.name == "Alfredo Pasta")
    )
    assert thursday_alfredo is not None and house_alfredo is not None
    assert thursday_alfredo.id != house_alfredo.id
    assert thursday_alfredo.price == Decimal("600.00")
    assert thursday_alfredo.day_of_week is DayOfWeek.thu
    assert house_alfredo.price == Decimal("550.00")
    assert house_alfredo.day_of_week is None
