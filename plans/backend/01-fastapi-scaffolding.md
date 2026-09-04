# 01 — FastAPI Scaffolding

**Purpose:** Stand up an empty-but-runnable FastAPI service: dependency setup, app factory, async DB plumbing, config, Alembic, lint/type/test tooling, and a single `/health` endpoint with a passing test. Runs against a **locally-installed PostgreSQL** (managed with pgAdmin / `psql`) — no Docker.

**Implements from `backend/CLAUDE.md`:** §2 (stack), §11 (structure), §12 (testing/lint/migrations), §13 phase 1.

**Prerequisites:** [00-overview.md](00-overview.md). PostgreSQL 18 installed and running on `localhost:5432` (service `postgresql-x64-18`); superuser role `postgres`. Python 3.12+ (3.13 present via the `py` launcher).

**Env/deps:** **`venv` + `pip`** (not `uv` — chosen for this machine). All commands below assume the project venv is active: `py -m venv .venv` then `.venv\Scripts\activate` (PowerShell) / `source .venv/Scripts/activate` (Git Bash). Dependencies are declared in `pyproject.toml` and installed with `pip install -e ".[dev]"`.

**Definition of done:**
- The `eatddelight` database exists on the local server (owner `postgres`); `alembic upgrade head` succeeds against an empty schema.
- `pytest tests/test_health.py` passes (hits `/api/v1/health`).
- `ruff check .`, `ruff format --check .`, `mypy app` all clean.
- `uvicorn app.main:app` serves `/docs` and `GET /api/v1/health` → `{"status":"ok"}`.

---

## 1. `pyproject.toml`

Single `pyproject.toml` at `backend/`. Managed with `venv` + `pip` — dev extras under `[project.optional-dependencies]` so `pip install -e ".[dev]"` works.

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "eatddelight-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy[asyncio]>=2.0.30",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "passlib[bcrypt]>=1.7.4",
    "pyjwt>=2.8",
    "jinja2>=3.1",
    "weasyprint>=62",
    "python-multipart>=0.0.9",
    "slowapi>=0.1.9",            # rate limiting, wired in the hardening pass
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
    "ruff>=0.5",
    "mypy>=1.10",
    "pre-commit>=3.7",
    "types-passlib",
]

[tool.hatch.build.targets.wheel]
packages = ["app"]

[tool.ruff]
target-version = "py312"
line-length = 100
src = ["app", "tests", "scripts"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "C4", "SIM", "ASYNC", "RUF"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]
mypy_path = "app"

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
disallow_incomplete_defs = false

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

> Note on JWT lib: plan uses **PyJWT** (`import jwt`). If `python-jose` is preferred later, only `app/core/security.py` changes.

## 2. `app/core/config.py`

```python
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    api_v1_prefix: str = "/api/v1"
    database_url: str
    test_database_url: str | None = None
    cors_origins: list[str] = Field(default_factory=list)

    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    owner_email: str
    owner_password: str
    owner_name: str = "Owner"
    whatsapp_number: str = "923122252915"

    rate_limit_public_write: str = "10/minute"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

`cors_origins` accepts a comma-separated env string (Pydantic v2 parses `list[str]` from JSON; add a `field_validator(mode="before")` to also accept `"a,b,c"`).

## 3. `app/db/base.py`

```python
from datetime import datetime
from sqlalchemy import MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
```

The naming convention matters for Alembic autogenerate stability.

## 4. `app/db/session.py`

```python
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import get_settings

_settings = get_settings()
engine = create_async_engine(_settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

Services own explicit transaction boundaries where they need atomicity; the `get_db` commit is the default happy-path commit for simple handlers.

## 5. `app/core/errors.py` (shell)

```python
class DomainError(Exception):
    status_code: int = 400
    code: str = "domain_error"

    def __init__(self, detail: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(detail)
        self.detail = detail
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
```

Concrete subclasses (`MinQuantityError`, `UnavailableItemError`, `AdvanceOrderError`, `DayOfWeekMismatchError`, `EmptyOrderError`, `AuthError`, `ForbiddenError`, `CategoryInUseError`) are added by the plan that first needs them; each sets `status_code` + `code` per the table in [00-overview.md](00-overview.md#66-error-shape).

Handlers (registered in `create_app`):

```python
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "code": exc.code})


async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code,
                        content={"detail": exc.detail, "code": "http_error"})


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422,
                        content={"detail": exc.errors(), "code": "validation_error"})
```

## 6. `app/api/v1/deps.py` (stubs for this phase)

Only `get_db` re-export and `get_session_token` are needed now:

```python
from typing import Annotated
from fastapi import Header
from app.db.session import get_db  # re-export

async def get_session_token(x_session_token: Annotated[str, Header(min_length=1)]) -> str:
    return x_session_token
```

`get_current_admin_user` / `require_role` are added in [05-admin-auth-crud-contact.md](05-admin-auth-crud-contact.md).

## 7. `app/api/v1/router.py` + health route

```python
# app/api/v1/endpoints/health.py
from fastapi import APIRouter
router = APIRouter(tags=["health"])

@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

```python
# app/api/v1/router.py
from fastapi import APIRouter
from app.api.v1.endpoints import health

api_router = APIRouter()
api_router.include_router(health.router)
# later plans append: settings, categories, menu, foods, cart, favourites, orders, contact, admin.*
```

## 8. `app/main.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import (
    DomainError, domain_error_handler, http_exception_handler, validation_exception_handler,
)
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Daughter's Delight API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins or ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
```

## 9. Local PostgreSQL setup (no Docker)

Use the PostgreSQL 18 server already installed on the machine (service `postgresql-x64-18`, `localhost:5432`), administered with **pgAdmin** or `psql` at `C:\Program Files\PostgreSQL\18\bin`. Do **not** add a `docker-compose.yml`. Superuser role is `postgres`.

**One-time setup — two databases owned by `postgres`:**

**A) pgAdmin (GUI):** connect as `postgres` → *Databases → Create → Database* → `eatddelight` (owner `postgres`); repeat for `eatddelight_test`.

**B) `psql` / CLI (equivalent):**
```powershell
$psql = "C:\Program Files\PostgreSQL\18\bin\psql.exe"
& $psql -U postgres -h localhost -d postgres -c "CREATE DATABASE eatddelight OWNER postgres;"
& $psql -U postgres -h localhost -d postgres -c "CREATE DATABASE eatddelight_test OWNER postgres;"
```
(`psql` will prompt for the `postgres` password; `scram-sha-256` auth is enforced in `pg_hba.conf`.)

**Then point `.env` at it:**
`DATABASE_URL=postgresql+asyncpg://postgres:<password>@localhost:5432/eatddelight`
`TEST_DATABASE_URL=postgresql+asyncpg://postgres:<password>@localhost:5432/eatddelight_test`
`DATABASE_URL` is the single source of truth; there are no separate `POSTGRES_*` container vars.

**Ongoing:** the service auto-starts with Windows; no per-session startup step. Verify with `& "C:\Program Files\PostgreSQL\18\bin\pg_isready.exe" -h localhost` or by connecting in pgAdmin.

## 10. Alembic

- `alembic init -t async alembic` (venv active)
- `alembic/env.py`: set `target_metadata = Base.metadata` (import `app.db.base.Base` **and** `import app.models` so every table is registered — plan 02 creates `app/models/__init__.py` that imports each module). Read the URL from `app.core.config.get_settings().database_url` instead of `alembic.ini`.
- `alembic.ini`: leave `sqlalchemy.url` blank / placeholder; env.py overrides it. Set `file_template` to `%%(year)d%%(month).2d%%(day).2d_%%(rev)s_%%(slug)s`.
- No versions yet in this phase — `alembic upgrade head` is a no-op that must still run cleanly.

## 11. `tests/conftest.py`

Responsibilities:
1. Build a settings object pointed at `TEST_DATABASE_URL` (`eatddelight_test`); create the test database if missing (connect to the `postgres` maintenance db, `CREATE DATABASE ...`). Since `eatddelight_test` is pre-created in setup, this fixture is normally a no-op.
2. Session-scoped: create a test engine, run `Base.metadata.create_all` (fast path) **or** `alembic upgrade head` (fidelity path — pick `create_all` for speed now, switch to alembic in CI once plan 02 lands migrations).
3. Function-scoped `db_session` fixture: open a connection, begin a transaction, bind an `AsyncSession` to it with a SAVEPOINT (`join_transaction_mode="create_savepoint"`), yield it, roll back after the test.
4. Function-scoped `client` fixture: `AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test")` with `app.dependency_overrides[get_db] = lambda: db_session`.
5. Factory fixtures (stubbed now, filled per plan): `make_category`, `make_food`, `make_addon`, `owner_user`, `staff_user`, `owner_client`, `staff_client`.

```python
# skeleton
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import create_app
from app.api.v1.deps import get_db

@pytest.fixture
async def client(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

## 12. `tests/test_health.py`

```python
async def test_health(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

## 13. `.pre-commit-config.yaml`

Hooks: `ruff` (lint, `--fix`), `ruff-format`, `mypy` (args `["app"]`), and a local `pytest -q` hook on `pre-push`. (Optional to `pre-commit install` locally; the config is committed regardless.)

## 14. Deliverables checklist

- [ ] `pyproject.toml` (deps + tool config); `.venv/` created, `pip install -e ".[dev]"` run — **no `uv.lock`**
- [ ] `.env.example` (from [00-overview.md §7](00-overview.md#7-environment-variables-envexample-contents)), `.env` locally (gitignored)
- [ ] `app/core/config.py`, `app/core/errors.py`
- [ ] `app/db/base.py`, `app/db/session.py`
- [ ] `app/api/v1/deps.py`, `app/api/v1/router.py`, `app/api/v1/endpoints/health.py`
- [ ] `app/main.py`, `app/__init__.py` (+ `__init__.py` in every package dir)
- [ ] Local `eatddelight` + `eatddelight_test` databases created (owner `postgres`) — **no `docker-compose.yml`**
- [ ] `alembic/` (init + async `env.py`), `alembic.ini`
- [ ] `tests/conftest.py`, `tests/test_health.py`
- [ ] `.pre-commit-config.yaml`, `.gitignore`, `README.md` (run instructions)
