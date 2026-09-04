from __future__ import annotations


async def test_submit_contact_message(client):
    resp = await client.post(
        "/api/v1/contact",
        json={"name": "Ali", "phone_or_email": "0300-1234567", "message": "When are you open?"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"]
    assert body.get("is_read") is False or "is_read" not in body


async def test_submit_contact_message_over_long_rejected(client):
    resp = await client.post(
        "/api/v1/contact",
        json={"name": "Ali", "phone_or_email": "0300-1234567", "message": "x" * 4001},
    )
    assert resp.status_code == 422


async def test_admin_contact_inbox_lists_and_filters(client, staff_client):
    resp = await client.post(
        "/api/v1/contact",
        json={"name": "Sara", "phone_or_email": "sara@test.local", "message": "Hi there"},
    )
    assert resp.status_code == 201
    message_id = resp.json()["id"]

    resp = await staff_client.get("/api/v1/admin/contact-messages")
    assert resp.status_code == 200
    assert any(m["id"] == message_id for m in resp.json())

    resp = await staff_client.get("/api/v1/admin/contact-messages", params={"is_read": "false"})
    assert any(m["id"] == message_id for m in resp.json())


async def test_mark_contact_message_read(client, staff_client):
    resp = await client.post(
        "/api/v1/contact",
        json={"name": "Bilal", "phone_or_email": "bilal@test.local", "message": "Menu?"},
    )
    message_id = resp.json()["id"]

    resp = await staff_client.patch(
        f"/api/v1/admin/contact-messages/{message_id}", json={"is_read": True}
    )
    assert resp.status_code == 200
    assert resp.json()["is_read"] is True

    resp = await staff_client.get("/api/v1/admin/contact-messages")
    updated = next(m for m in resp.json() if m["id"] == message_id)
    assert updated["is_read"] is True


async def test_unauthenticated_contact_inbox_401(client):
    resp = await client.get("/api/v1/admin/contact-messages")
    assert resp.status_code == 401
