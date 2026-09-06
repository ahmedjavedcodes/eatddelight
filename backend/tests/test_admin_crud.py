from __future__ import annotations

from decimal import Decimal

# --- Categories ---


async def test_create_category_appears_in_admin_list(staff_client):
    resp = await staff_client.post(
        "/api/v1/admin/categories", json={"name": "Beverages", "display_order": 5}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "beverages"

    resp = await staff_client.get("/api/v1/admin/categories")
    assert any(c["id"] == body["id"] for c in resp.json())


async def test_create_category_slug_conflict(staff_client):
    resp = await staff_client.post("/api/v1/admin/categories", json={"name": "Snacks"})
    assert resp.status_code == 201
    resp = await staff_client.post("/api/v1/admin/categories", json={"name": "Snacks"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "slug_conflict"


async def test_delete_category_with_foods_conflict(owner_client, make_food):
    food = await make_food()
    resp = await owner_client.delete(f"/api/v1/admin/categories/{food.category_id}")
    assert resp.status_code == 409
    assert resp.json()["code"] == "category_in_use"


# --- Foods ---


async def test_create_food_bad_category_id(staff_client):
    resp = await staff_client.post(
        "/api/v1/admin/foods",
        json={"category_id": 999999, "name": "Ghost Dish", "price": "100.00"},
    )
    assert resp.status_code == 404


async def test_create_food_zero_price_rejected(staff_client, make_category):
    category = await make_category()
    resp = await staff_client.post(
        "/api/v1/admin/foods",
        json={"category_id": category.id, "name": "Free Dish", "price": "0.00"},
    )
    assert resp.status_code == 422


async def test_patch_food_availability(staff_client, make_food):
    food = await make_food(is_available=True)
    resp = await staff_client.patch(
        f"/api/v1/admin/foods/{food.id}/availability", json={"is_available": False}
    )
    assert resp.status_code == 200
    assert resp.json()["is_available"] is False


# --- Food variants ---


async def test_create_food_with_variants_sets_min_price(staff_client, make_category):
    category = await make_category()
    resp = await staff_client.post(
        "/api/v1/admin/foods",
        json={
            "category_id": category.id,
            "name": "Chicken Karahi",
            "price": "800.00",
            "variants": [
                {"label": "500g", "price": "800.00"},
                {"label": "1kg", "price": "2000.00"},
                {"label": "2kg", "price": "3000.00"},
            ],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert Decimal(body["price"]) == Decimal("800.00")
    assert [v["label"] for v in body["variants"]] == ["500g", "1kg", "2kg"]
    assert [Decimal(v["price"]) for v in body["variants"]] == [
        Decimal("800.00"),
        Decimal("2000.00"),
        Decimal("3000.00"),
    ]


async def test_create_food_duplicate_variant_prices_rejected(staff_client, make_category):
    category = await make_category()
    resp = await staff_client.post(
        "/api/v1/admin/foods",
        json={
            "category_id": category.id,
            "name": "Confused Karahi",
            "price": "800.00",
            "variants": [
                {"label": "500g", "price": "800.00"},
                {"label": "1kg", "price": "800.00"},
            ],
        },
    )
    assert resp.status_code == 422


async def test_create_food_duplicate_variant_labels_rejected(staff_client, make_category):
    category = await make_category()
    resp = await staff_client.post(
        "/api/v1/admin/foods",
        json={
            "category_id": category.id,
            "name": "Confused Karahi",
            "price": "800.00",
            "variants": [
                {"label": "1kg", "price": "800.00"},
                {"label": "1kg", "price": "2000.00"},
            ],
        },
    )
    assert resp.status_code == 422


async def test_update_food_replaces_variants(staff_client, make_food):
    food = await make_food(price=Decimal("500.00"))
    resp = await staff_client.put(
        f"/api/v1/admin/foods/{food.id}",
        json={
            "variants": [{"label": "Half", "price": "300.00"}, {"label": "Full", "price": "500.00"}]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["variants"]) == 2
    assert Decimal(body["price"]) == Decimal("300.00")

    resp = await staff_client.put(
        f"/api/v1/admin/foods/{food.id}",
        json={"variants": [{"label": "Only Size", "price": "450.00"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["variants"]) == 1
    assert body["variants"][0]["label"] == "Only Size"


async def test_update_food_clear_variants_keeps_existing_price(staff_client, make_food):
    food = await make_food(price=Decimal("500.00"))
    resp = await staff_client.put(
        f"/api/v1/admin/foods/{food.id}",
        json={"variants": [{"label": "Half", "price": "300.00"}]},
    )
    assert resp.status_code == 200
    assert Decimal(resp.json()["price"]) == Decimal("300.00")

    resp = await staff_client.put(f"/api/v1/admin/foods/{food.id}", json={"variants": []})
    assert resp.status_code == 200
    body = resp.json()
    assert body["variants"] == []
    assert Decimal(body["price"]) == Decimal("300.00")


async def test_update_food_without_variants_key_leaves_variants_untouched(staff_client, make_food):
    food = await make_food(price=Decimal("500.00"))
    resp = await staff_client.put(
        f"/api/v1/admin/foods/{food.id}",
        json={"variants": [{"label": "Half", "price": "300.00"}]},
    )
    assert resp.status_code == 200

    resp = await staff_client.put(f"/api/v1/admin/foods/{food.id}", json={"name": "Renamed Only"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Renamed Only"
    assert len(body["variants"]) == 1


# --- AddOns ---


async def test_addon_food_ids_sync(staff_client, make_food):
    food = await make_food()
    resp = await staff_client.post(
        "/api/v1/admin/addons",
        json={"name": "Extra Cheese", "price": "50.00", "food_ids": [food.id]},
    )
    assert resp.status_code == 201


# --- Orders ---


async def test_order_status_forward_transitions(owner_client, make_order):
    order = await make_order()
    resp = await owner_client.patch(
        f"/api/v1/admin/orders/{order.id}/status", json={"status": "confirmed"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"

    resp = await owner_client.patch(
        f"/api/v1/admin/orders/{order.id}/status", json={"status": "pending"}
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "invalid_status_transition"

    resp = await owner_client.patch(
        f"/api/v1/admin/orders/{order.id}/status", json={"status": "completed"}
    )
    assert resp.status_code == 200

    resp = await owner_client.patch(
        f"/api/v1/admin/orders/{order.id}/status", json={"status": "cancelled"}
    )
    assert resp.status_code == 409


async def test_order_status_cancel_from_pending(owner_client, make_order):
    order = await make_order()
    resp = await owner_client.patch(
        f"/api/v1/admin/orders/{order.id}/status", json={"status": "cancelled"}
    )
    assert resp.status_code == 200


async def test_quote_custom_order_sets_total(owner_client, make_order):
    order = await make_order(order_source="custom_request", is_custom=True)
    resp = await owner_client.patch(
        f"/api/v1/admin/orders/{order.id}/quote", json={"total": "750.00"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert Decimal(body["total"]) == Decimal("750.00")
    assert body["status"] == "confirmed"


async def test_quote_non_custom_order_rejected(owner_client, make_order):
    order = await make_order(order_source="catalog", is_custom=False)
    resp = await owner_client.patch(
        f"/api/v1/admin/orders/{order.id}/quote", json={"total": "750.00"}
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "not_a_custom_order"


# --- Staff ---


async def test_create_staff_can_login_then_deactivate_blocks_token(owner_client, client):
    resp = await owner_client.post(
        "/api/v1/admin/staff",
        json={"name": "New Staff", "email": "newstaff@test.local", "password": "password123"},
    )
    assert resp.status_code == 201
    staff_id = resp.json()["id"]

    resp = await client.post(
        "/api/v1/admin/auth/login",
        json={"email": "newstaff@test.local", "password": "password123"},
    )
    assert resp.status_code == 200
    access_token = resp.json()["access_token"]

    resp = await owner_client.patch(f"/api/v1/admin/staff/{staff_id}", json={"is_active": False})
    assert resp.status_code == 200

    resp = await client.get(
        "/api/v1/admin/categories", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 401


async def test_cannot_deactivate_last_active_owner(owner_client, owner_user):
    resp = await owner_client.patch(
        f"/api/v1/admin/staff/{owner_user.id}", json={"is_active": False}
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "last_owner"
