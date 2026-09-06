from __future__ import annotations

import io

from app.core.config import get_settings


async def test_upload_image_success(staff_client, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "media_root", str(tmp_path))

    resp = await staff_client.post(
        "/api/v1/admin/uploads/image",
        files={"file": ("dish.png", io.BytesIO(b"not-really-a-png"), "image/png")},
    )
    assert resp.status_code == 200
    url = resp.json()["url"]
    assert url.startswith("/media/uploads/")
    assert url.endswith(".png")

    saved_path = tmp_path / "uploads" / url.rsplit("/", 1)[-1]
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"not-really-a-png"


async def test_upload_image_rejects_oversized(staff_client, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "media_root", str(tmp_path))
    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)

    oversized = b"x" * (2 * 1024 * 1024)
    resp = await staff_client.post(
        "/api/v1/admin/uploads/image",
        files={"file": ("big.jpg", io.BytesIO(oversized), "image/jpeg")},
    )
    assert resp.status_code == 413
    assert resp.json()["code"] == "upload_too_large"
    assert list((tmp_path / "uploads").iterdir()) == []


async def test_upload_image_rejects_unsupported_type(staff_client, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "media_root", str(tmp_path))

    resp = await staff_client.post(
        "/api/v1/admin/uploads/image",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert resp.status_code == 415
    assert resp.json()["code"] == "unsupported_image_type"


async def test_upload_image_requires_auth(client, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "media_root", str(tmp_path))

    resp = await client.post(
        "/api/v1/admin/uploads/image",
        files={"file": ("dish.png", io.BytesIO(b"data"), "image/png")},
    )
    assert resp.status_code in (401, 403)
