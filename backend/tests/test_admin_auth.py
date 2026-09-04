from __future__ import annotations

from app.core.security import create_access_token, create_refresh_token


async def test_login_success(client, owner_user):
    resp = await client.post(
        "/api/v1/admin/auth/login",
        json={"email": owner_user.email, "password": "password123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["role"] == "owner"


async def test_login_wrong_password(client, owner_user):
    resp = await client.post(
        "/api/v1/admin/auth/login",
        json={"email": owner_user.email, "password": "wrong"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "unauthorized"


async def test_login_unknown_email_same_body_shape(client):
    resp = await client.post(
        "/api/v1/admin/auth/login",
        json={"email": "nobody@test.local", "password": "whatever"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "unauthorized"


async def test_login_deactivated_user(client, staff_user, db_session):
    staff_user.is_active = False
    await db_session.flush()
    resp = await client.post(
        "/api/v1/admin/auth/login",
        json={"email": staff_user.email, "password": "password123"},
    )
    assert resp.status_code == 401


async def test_protected_route_requires_bearer(client):
    resp = await client.get("/api/v1/admin/categories")
    assert resp.status_code == 401


async def test_protected_route_rejects_malformed_token(client):
    resp = await client.get(
        "/api/v1/admin/categories", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert resp.status_code == 401


async def test_protected_route_rejects_refresh_token_as_access(client, owner_user):
    refresh = create_refresh_token(owner_user.id, owner_user.role.value)
    resp = await client.get(
        "/api/v1/admin/categories", headers={"Authorization": f"Bearer {refresh}"}
    )
    assert resp.status_code == 401


async def test_refresh_issues_new_pair(client, owner_user):
    refresh = create_refresh_token(owner_user.id, owner_user.role.value)
    resp = await client.post("/api/v1/admin/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]


async def test_refresh_rejects_access_token(client, owner_user):
    access = create_access_token(owner_user.id, owner_user.role.value)
    resp = await client.post("/api/v1/admin/auth/refresh", json={"refresh_token": access})
    assert resp.status_code == 401
