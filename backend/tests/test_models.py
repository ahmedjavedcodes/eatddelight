from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    DayOfWeek,
    Favourite,
    Order,
    OrderItem,
    OrderSource,
    OrderStatus,
    SiteSettings,
)


async def test_category_food_one_to_many(db_session, make_category, make_food):
    category = await make_category()
    for _ in range(3):
        await make_food(category=category)

    await db_session.refresh(category, ["foods"])
    assert len(category.foods) == 3
    assert all(f.category_id == category.id for f in category.foods)
    assert category.foods[0].category is category


async def test_food_addons_raw_relationship_excludes_global(db_session, make_food, make_addon):
    food = await make_food()
    specific = await make_addon(is_global=False)
    await make_addon(is_global=True)  # global add-ons are resolved in the service layer

    await db_session.refresh(food, ["addons"])  # load the (empty) collection in-context
    food.addons.append(specific)
    await db_session.flush()
    await db_session.refresh(food, ["addons"])
    assert [a.id for a in food.addons] == [specific.id]


async def test_favourite_unique_pair(db_session, make_food):
    food = await make_food()
    db_session.add(Favourite(session_token="tok", food_id=food.id))
    await db_session.flush()

    db_session.add(Favourite(session_token="tok", food_id=food.id))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_category_delete_is_restricted(db_session, make_category, make_food):
    category = await make_category()
    await make_food(category=category)

    await db_session.delete(category)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_site_settings_singleton(db_session):
    db_session.add(
        SiteSettings(
            id=1,
            business_name="D",
            contact_phone="p",
            whatsapp_number="w",
            instagram_handle="i",
        )
    )
    await db_session.flush()

    db_session.add(
        SiteSettings(
            id=2,
            business_name="D2",
            contact_phone="p",
            whatsapp_number="w",
            instagram_handle="i",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


def test_order_status_values():
    assert {s.value for s in OrderStatus} == {
        "pending",
        "confirmed",
        "completed",
        "cancelled",
    }


async def test_price_round_trips_as_two_place_decimal(db_session, make_food):
    food = await make_food(price=Decimal("380.5"))
    await db_session.flush()
    await db_session.refresh(food)

    assert food.price == Decimal("380.50")
    assert food.price.as_tuple().exponent == -2


async def test_order_item_unit_price_is_a_snapshot(db_session, make_food):
    food = await make_food(price=Decimal("400.00"))
    order = Order(
        invoice_number="DD-20260904-0001",
        lookup_token="tok-1",
        customer_name="A",
        customer_phone="0300",
        order_source=OrderSource.catalog,
        requested_date=date(2026, 9, 10),
    )
    order.items.append(
        OrderItem(food_id=food.id, food_name=food.name, quantity=3, unit_price=food.price)
    )
    db_session.add(order)
    await db_session.flush()
    item_id = order.items[0].id

    item = order.items[0]
    food.price = Decimal("999.00")
    await db_session.flush()
    await db_session.refresh(item)

    assert item.unit_price == Decimal("400.00")
    assert item_id == item.id


async def test_deleting_food_nulls_order_item_and_keeps_snapshot(db_session, make_food):
    food = await make_food(price=Decimal("400.00"))
    order = Order(
        invoice_number="DD-20260904-0002",
        lookup_token="tok-2",
        customer_name="A",
        customer_phone="0300",
        order_source=OrderSource.catalog,
        requested_date=date(2026, 9, 10),
    )
    order.items.append(
        OrderItem(
            food_id=food.id,
            food_name="Snapshot Name",
            quantity=3,
            unit_price=Decimal("400.00"),
        )
    )
    db_session.add(order)
    await db_session.flush()
    item_id = order.items[0].id

    item = order.items[0]
    await db_session.delete(food)
    await db_session.flush()
    await db_session.refresh(item)

    assert item.id == item_id
    assert item.food_id is None
    assert item.food_name == "Snapshot Name"


async def test_order_custom_fields_are_nullable(db_session):
    order = Order(
        invoice_number="DD-20260904-0003",
        lookup_token="tok-3",
        customer_name="A",
        customer_phone="0300",
        order_source=OrderSource.custom_request,
        requested_date=date(2026, 9, 10),
        is_custom=True,
        custom_description="A bespoke cake",
    )
    db_session.add(order)
    await db_session.flush()

    assert order.servings is None
    assert order.budget_range is None
    assert order.occasion is None
    assert order.event_date is None
    assert order.subtotal is None
    assert order.total is None
    assert order.status is OrderStatus.pending


async def test_day_of_week_enum_persists(db_session, make_food):
    food = await make_food(day_of_week=DayOfWeek.mon)
    await db_session.flush()
    await db_session.refresh(food)

    assert food.day_of_week is DayOfWeek.mon
