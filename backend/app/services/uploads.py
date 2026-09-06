"""Local-disk storage for admin-uploaded product images.

Files are saved under ``<media_root>/uploads/<uuid>.<ext>`` and served back by
the static file mount at ``/media`` (see ``app.main``). No cloud storage is
used - this matches the project's local-first setup.
"""

import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.errors import UnsupportedImageTypeError, UploadTooLargeError

_ALLOWED_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

_CHUNK_SIZE = 1024 * 1024


def _uploads_dir() -> Path:
    settings = get_settings()
    path = Path(settings.media_root) / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


async def save_image_upload(file: UploadFile) -> str:
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024

    ext = _ALLOWED_CONTENT_TYPES.get(file.content_type or "")
    if ext is None:
        raise UnsupportedImageTypeError("only JPEG, PNG, and WEBP images are supported")

    destination = _uploads_dir() / f"{uuid.uuid4().hex}.{ext}"
    size = 0
    try:
        with destination.open("wb") as out_file:
            while chunk := await file.read(_CHUNK_SIZE):
                size += len(chunk)
                if size > max_bytes:
                    raise UploadTooLargeError(
                        f"image must be {settings.max_upload_mb}MB or smaller"
                    )
                out_file.write(chunk)
    except UploadTooLargeError:
        destination.unlink(missing_ok=True)
        raise

    return f"/media/uploads/{destination.name}"
