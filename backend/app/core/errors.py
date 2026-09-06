"""Domain error base class and the JSON exception handlers.

Every handled error is rendered as ``{"detail": ..., "code": <stable_snake_case>}``.
Concrete ``DomainError`` subclasses are added by the plan that first needs them.
"""

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request


class DomainError(Exception):
    """Base class for business-rule violations that map to a JSON error body."""

    status_code: int = 400
    code: str = "domain_error"

    def __init__(
        self,
        detail: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class AuthError(DomainError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(DomainError):
    status_code = 403
    code = "forbidden"


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class SlugConflictError(DomainError):
    status_code = 409
    code = "slug_conflict"


class CategoryInUseError(DomainError):
    status_code = 409
    code = "category_in_use"


class EmailConflictError(DomainError):
    status_code = 409
    code = "email_conflict"


class InvalidStatusTransitionError(DomainError):
    status_code = 409
    code = "invalid_status_transition"


class NotACustomOrderError(DomainError):
    status_code = 409
    code = "not_a_custom_order"


class LastOwnerError(DomainError):
    status_code = 409
    code = "last_owner"


class UploadTooLargeError(DomainError):
    status_code = 413
    code = "upload_too_large"


class UnsupportedImageTypeError(DomainError):
    status_code = 415
    code = "unsupported_image_type"


async def domain_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, DomainError):  # pragma: no cover - defensive
        raise exc
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
    )


async def http_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):  # pragma: no cover - defensive
        raise exc
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": "http_error"},
    )


async def validation_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):  # pragma: no cover - defensive
        raise exc
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(exc.errors()), "code": "validation_error"},
    )
