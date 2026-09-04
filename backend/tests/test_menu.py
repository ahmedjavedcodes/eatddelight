from __future__ import annotations

from app.models import food_addons
from scripts.seed_menu import seed


async def test_settings_returns_seeded_business_info(client, db_session):
    await seed(db_session)
    resp = await client.get("/api/v1/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["business_name"] == "Daughter's Delight"
    assert body["whatsapp_number"] == "923122252915"


async def test_settings_404_when_not_seeded(client):
    resp = await client.get("/api/v1/settings")
    assert resp.status_code == 404


async def test_categories_excludes_weekly_when_flagged(client, db_session):
    await seed(db_session)
    resp = await client.get("/api/v1/categories")
    assert resp.status_code == 200
    assert len(resp.json()) == 11

    resp = await client.get("/api/v1/categories", params={"exclude_weekly": "true"})
    assert len(resp.json()) == 10
    assert all(c["slug"] != "menu-of-the-day" for c in resp.json())


async def test_category_foods_404_for_unknown(client):
    resp = await client.get("/api/v1/categories/999999/foods")
    assert resp.status_code == 404


async def test_category_foods_lists_that_categorys_foods(client, db_session):
    await seed(db_session)
    resp = await client.get("/api/v1/categories")
    house_favourites = next(c for c in resp.json() if c["slug"] == "house-favourites")

    resp = await client.get(f"/api/v1/categories/{house_favourites['id']}/foods")
    names = {f["name"] for f in resp.json()}
    assert names == {"Alfredo Pasta", "Chicken Raps"}


async def test_get_menu_excludes_weekly_and_groups_by_category(client, db_session):
    await seed(db_session)
    resp = await client.get("/api/v1/menu")
    assert resp.status_code == 200
    groups = resp.json()
    assert len(groups) == 10
    assert all(g["slug"] != "menu-of-the-day" for g in groups)
    assert all(g["foods"] for g in groups)

    house_favourites = next(g for g in groups if g["slug"] == "house-favourites")
    alfredo = next(f for f in house_favourites["foods"] if f["name"] == "Alfredo Pasta")
    assert alfredo["price"] == "550.00"


async def test_get_weekly_menu_five_days_in_order(client, db_session):
    await seed(db_session)
    resp = await client.get("/api/v1/weekly-menu")
    assert resp.status_code == 200
    groups = resp.json()
    assert [g["day_of_week"] for g in groups] == ["mon", "tue", "wed", "thu", "fri"]

    thursday = groups[3]
    assert thursday["food"]["name"] == "Alfredo Pasta with Sauce"
    assert thursday["food"]["price"] == "600.00"


async def test_foods_search_matches_both_duplicate_dishes(client, db_session):
    await seed(db_session)
    resp = await client.get("/api/v1/foods", params={"search": "biryani"})
    names = {f["name"] for f in resp.json()}
    assert "Chicken Biryani" in names
    assert "Chicken Biryani with Raita + Salad" in names


async def test_foods_filter_by_day_of_week(client, db_session):
    await seed(db_session)
    resp = await client.get("/api/v1/foods", params={"day_of_week": "fri"})
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "Chicken Biryani with Raita + Salad"


async def test_foods_filter_by_category_and_availability(client, db_session):
    await seed(db_session)
    resp = await client.get("/api/v1/categories")
    rice = next(c for c in resp.json() if c["slug"] == "rice")

    resp = await client.get(
        "/api/v1/foods", params={"category_id": rice["id"], "available": "true"}
    )
    assert len(resp.json()) == 5
    assert all(f["category_id"] == rice["id"] for f in resp.json())


async def test_food_detail_404_for_unknown(client):
    resp = await client.get("/api/v1/foods/999999")
    assert resp.status_code == 404


async def test_food_detail_resolves_global_and_specific_addons(
    client, db_session, make_food, make_addon
):
    food = await make_food()
    global_addon = await make_addon(is_global=True)
    specific_addon = await make_addon(is_global=False)
    unavailable_addon = await make_addon(is_global=True, is_available=False)
    await db_session.execute(
        food_addons.insert().values(food_id=food.id, addon_id=specific_addon.id)
    )
    await db_session.flush()

    resp = await client.get(f"/api/v1/foods/{food.id}")
    assert resp.status_code == 200
    addon_names = {a["name"] for a in resp.json()["addons"]}
    assert addon_names == {global_addon.name, specific_addon.name}
    assert unavailable_addon.name not in addon_names
