from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import CategoryInUseError, NotFoundError, SlugConflictError
from app.models import AddOn, Category, Food, FoodVariant, food_addons
from app.schemas.admin import (
    AddOnCreate,
    AddOnUpdate,
    CategoryCreate,
    CategoryUpdate,
    FoodCreate,
    FoodUpdate,
    FoodVariantIn,
)
from app.services.slug import slugify

# --- Category ---


async def _slug_exists(session: AsyncSession, slug: str, *, exclude_id: int | None = None) -> bool:
    stmt = select(Category.id).where(Category.slug == slug)
    if exclude_id is not None:
        stmt = stmt.where(Category.id != exclude_id)
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def create_category(session: AsyncSession, payload: CategoryCreate) -> Category:
    slug = slugify(payload.name)
    if await _slug_exists(session, slug):
        raise SlugConflictError(f"a category with slug '{slug}' already exists")
    category = Category(
        name=payload.name,
        slug=slug,
        description=payload.description,
        display_order=payload.display_order,
        is_active=payload.is_active,
    )
    session.add(category)
    await session.flush()
    return category


async def get_category_or_404(session: AsyncSession, category_id: int) -> Category:
    category = await session.get(Category, category_id)
    if category is None:
        raise NotFoundError("category not found")
    return category


async def update_category(
    session: AsyncSession, category_id: int, payload: CategoryUpdate
) -> Category:
    category = await get_category_or_404(session, category_id)
    data = payload.model_dump(exclude_unset=True, exclude={"regenerate_slug"})
    for field, value in data.items():
        setattr(category, field, value)
    if payload.regenerate_slug and payload.name is not None:
        new_slug = slugify(payload.name)
        if await _slug_exists(session, new_slug, exclude_id=category.id):
            raise SlugConflictError(f"a category with slug '{new_slug}' already exists")
        category.slug = new_slug
    await session.flush()
    return category


async def delete_category(session: AsyncSession, category_id: int) -> None:
    category = await get_category_or_404(session, category_id)
    await session.delete(category)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise CategoryInUseError("category has foods and cannot be deleted") from exc


# --- Food ---


async def _sync_variants(session: AsyncSession, food: Food, variants: list[FoodVariantIn]) -> None:
    """Replace all of a food's variants with the given list.

    Historical OrderItem rows keep their own price/label snapshot and their
    ``variant_id`` FK is ``ON DELETE SET NULL``, so wiping and recreating here
    never corrupts past orders.
    """
    await session.execute(delete(FoodVariant).where(FoodVariant.food_id == food.id))
    for order, variant in enumerate(variants):
        session.add(
            FoodVariant(
                food_id=food.id,
                label=variant.label,
                price=variant.price,
                display_order=order,
            )
        )
    await session.flush()


async def create_food(session: AsyncSession, payload: FoodCreate) -> Food:
    await get_category_or_404(session, payload.category_id)
    data = payload.model_dump(exclude={"variants"})
    if payload.variants:
        data["price"] = min(v.price for v in payload.variants)
    food = Food(**data)
    session.add(food)
    await session.flush()
    if payload.variants:
        await _sync_variants(session, food, payload.variants)
    await session.refresh(food, attribute_names=["variants"])
    return food


async def get_food_or_404(session: AsyncSession, food_id: int) -> Food:
    food = await session.get(Food, food_id)
    if food is None:
        raise NotFoundError("food not found")
    return food


async def update_food(session: AsyncSession, food_id: int, payload: FoodUpdate) -> Food:
    food = await get_food_or_404(session, food_id)
    data = payload.model_dump(exclude_unset=True, exclude={"variants"})
    if "category_id" in data:
        await get_category_or_404(session, data["category_id"])
    for field, value in data.items():
        setattr(food, field, value)

    if "variants" in payload.model_fields_set:
        variants = payload.variants or []
        await _sync_variants(session, food, variants)
        if variants:
            food.price = min(v.price for v in variants)

    await session.flush()
    await session.refresh(food, attribute_names=["variants"])
    return food


async def set_food_availability(session: AsyncSession, food_id: int, is_available: bool) -> Food:
    food = await get_food_or_404(session, food_id)
    food.is_available = is_available
    await session.flush()
    await session.refresh(food, attribute_names=["variants"])
    return food


async def delete_food(session: AsyncSession, food_id: int) -> None:
    food = await get_food_or_404(session, food_id)
    await session.delete(food)
    await session.flush()


# --- AddOn ---


async def _sync_food_links(session: AsyncSession, addon: AddOn, food_ids: list[int]) -> None:
    await session.execute(food_addons.delete().where(food_addons.c.addon_id == addon.id))
    if not food_ids:
        return
    existing = (await session.execute(select(Food.id).where(Food.id.in_(food_ids)))).scalars().all()
    missing = set(food_ids) - set(existing)
    if missing:
        raise NotFoundError(f"food(s) not found: {sorted(missing)}")
    await session.execute(
        food_addons.insert(),
        [{"food_id": fid, "addon_id": addon.id} for fid in food_ids],
    )


async def create_addon(session: AsyncSession, payload: AddOnCreate) -> AddOn:
    addon = AddOn(
        name=payload.name,
        price=payload.price,
        is_available=payload.is_available,
        is_global=payload.is_global,
    )
    session.add(addon)
    await session.flush()
    if not payload.is_global and payload.food_ids:
        await _sync_food_links(session, addon, payload.food_ids)
    await session.flush()
    return addon


async def get_addon_or_404(session: AsyncSession, addon_id: int) -> AddOn:
    addon = await session.get(AddOn, addon_id)
    if addon is None:
        raise NotFoundError("add-on not found")
    return addon


async def update_addon(session: AsyncSession, addon_id: int, payload: AddOnUpdate) -> AddOn:
    addon = await get_addon_or_404(session, addon_id)
    data = payload.model_dump(exclude_unset=True, exclude={"food_ids"})
    for field, value in data.items():
        setattr(addon, field, value)
    if payload.food_ids is not None:
        await _sync_food_links(session, addon, payload.food_ids)
    await session.flush()
    return addon


async def delete_addon(session: AsyncSession, addon_id: int) -> None:
    addon = await get_addon_or_404(session, addon_id)
    await session.delete(addon)
    await session.flush()
