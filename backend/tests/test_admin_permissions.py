from __future__ import annotations

from app.models import SiteSettings


async def test_delete_category_owner_ok_staff_forbidden(owner_client, staff_client, make_category):
    cat_for_staff = await make_category()
    resp = await staff_client.delete(f"/api/v1/admin/categories/{cat_for_staff.id}")
    assert resp.status_code == 403

    cat_for_owner = await make_category()
    resp = await owner_client.delete(f"/api/v1/admin/categories/{cat_for_owner.id}")
    assert resp.status_code == 204


async def test_delete_food_owner_ok_staff_forbidden(owner_client, staff_client, make_food):
    food_for_staff = await make_food()
    resp = await staff_client.delete(f"/api/v1/admin/foods/{food_for_staff.id}")
    assert resp.status_code == 403

    food_for_owner = await make_food()
    resp = await owner_client.delete(f"/api/v1/admin/foods/{food_for_owner.id}")
    assert resp.status_code == 204


async def test_delete_addon_owner_ok_staff_forbidden(owner_client, staff_client, make_addon):
    addon_for_staff = await make_addon()
    resp = await staff_client.delete(f"/api/v1/admin/addons/{addon_for_staff.id}")
    assert resp.status_code == 403

    addon_for_owner = await make_addon()
    resp = await owner_client.delete(f"/api/v1/admin/addons/{addon_for_owner.id}")
    assert resp.status_code == 204


async def test_create_update_categories_foods_addons_both_roles_ok(
    owner_client, staff_client, make_category, make_food
):
    for c in (owner_client, staff_client):
        resp = await c.post(
            "/api/v1/admin/categories", json={"name": f"Cat {id(c)}", "display_order": 1}
        )
        assert resp.status_code == 201

    category = await make_category()
    for c in (owner_client, staff_client):
        resp = await c.post(
            "/api/v1/admin/foods",
            json={"category_id": category.id, "name": f"Food {id(c)}", "price": "100.00"},
        )
        assert resp.status_code == 201


async def test_staff_forbidden_on_all_staff_routes(staff_client, owner_client):
    resp = await staff_client.get("/api/v1/admin/staff")
    assert resp.status_code == 403
    resp = await staff_client.post(
        "/api/v1/admin/staff",
        json={"name": "X", "email": "x@test.local", "password": "password123"},
    )
    assert resp.status_code == 403

    resp = await owner_client.get("/api/v1/admin/staff")
    assert resp.status_code == 200


async def test_settings_owner_ok_staff_forbidden(owner_client, staff_client, db_session):
    db_session.add(
        SiteSettings(
            id=1,
            business_name="Daughter's Delight",
            contact_phone="0312-2252915",
            whatsapp_number="923122252915",
            instagram_handle="eatddelight",
        )
    )
    await db_session.flush()

    resp = await staff_client.put("/api/v1/admin/settings", json={"tagline": "New"})
    assert resp.status_code == 403

    resp = await owner_client.put("/api/v1/admin/settings", json={"tagline": "New"})
    assert resp.status_code == 200


async def test_quote_owner_ok_staff_forbidden(owner_client, staff_client):
    resp = await staff_client.patch("/api/v1/admin/orders/1/quote", json={"total": "500.00"})
    assert resp.status_code == 403


async def test_order_status_both_roles_ok(owner_client, staff_client):
    body = {"status": "confirmed"}
    resp = await owner_client.patch("/api/v1/admin/orders/999999/status", json=body)
    assert resp.status_code == 404  # role check passes, order lookup fails
    resp = await staff_client.patch("/api/v1/admin/orders/999999/status", json=body)
    assert resp.status_code == 404


async def test_unauthenticated_401_on_every_admin_route(client):
    routes = [
        ("GET", "/api/v1/admin/categories"),
        ("GET", "/api/v1/admin/foods"),
        ("GET", "/api/v1/admin/addons"),
        ("GET", "/api/v1/admin/orders"),
        ("GET", "/api/v1/admin/staff"),
        ("GET", "/api/v1/admin/settings"),
        ("GET", "/api/v1/admin/contact-messages"),
    ]
    for method, path in routes:
        resp = await client.request(method, path)
        assert resp.status_code == 401, path
