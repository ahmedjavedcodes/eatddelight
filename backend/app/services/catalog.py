from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AddOn, Food, food_addons


async def resolve_addons_for_food(session: AsyncSession, food: Food) -> list[AddOn]:
    """Global add-ons union this food's explicit links, available only, name-ordered."""
    stmt = (
        select(AddOn)
        .where(
            or_(
                AddOn.is_global.is_(True),
                AddOn.id.in_(
                    select(food_addons.c.addon_id).where(food_addons.c.food_id == food.id)
                ),
            )
        )
        .where(AddOn.is_available.is_(True))
        .order_by(AddOn.name)
    )
    return list((await session.execute(stmt)).scalars().all())
