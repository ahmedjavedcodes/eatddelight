"""Shared test fixtures.

- A dedicated Postgres test database (``TEST_DATABASE_URL`` -> ``eatddelight_test``),
  created if missing; the ``public`` schema is dropped and rebuilt once per session
  by running ``alembic upgrade head`` in a subprocess (so tests exercise the real
  migrations without nesting event loops).
- Per-test isolation via a SAVEPOINT that is rolled back on teardown.
- All async fixtures and tests share the session event loop (see pyproject).
- An ``httpx.AsyncClient`` bound to the ASGI app with ``get_db`` overridden.
- Factory fixtures: ``make_category`` / ``make_food`` / ``make_addon``.
"""

from __future__ import annotations

import itertools
import os
import subprocess
import sys
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import asyncpg
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.v1.deps import get_db
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.main import create_app
from app.models import AddOn, AdminRole, AdminUser, Category, Food, Order, OrderSource

_ROOT = Path(__file__).resolve().parent.parent


def _test_database_url() -> str:
    settings = get_settings()
    url = settings.test_database_url or settings.database_url
    if url == settings.database_url:
        raise RuntimeError(
            "TEST_DATABASE_URL is not set; refusing to run the suite against the dev "
            "database. Set it in .env (e.g. .../eatddelight_test)."
        )
    return url


def _pg_dsn(async_url: str, *, database: str | None = None) -> str:
    url = make_url(async_url)
    name = database or url.database
    return f"postgresql://{url.username}:{url.password}@{url.host}:{url.port or 5432}/{name}"


async def _ensure_database(async_url: str) -> None:
    db_name = make_url(async_url).database
    assert db_name is not None
    conn = await asyncpg.connect(_pg_dsn(async_url, database="postgres"))
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await conn.close()


async def _reset_public_schema(async_url: str) -> None:
    conn = await asyncpg.connect(_pg_dsn(async_url))
    try:
        await conn.execute("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
    finally:
        await conn.close()


def _run_alembic_upgrade(url: str) -> None:
    env = {**os.environ, "ALEMBIC_DATABASE_URL": url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_ROOT,
        env=env,
        check=True,
        capture_output=True,
    )


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _engine() -> AsyncGenerator[AsyncEngine, None]:
    url = _test_database_url()
    await _ensure_database(url)
    await _reset_public_schema(url)
    _run_alembic_upgrade(url)
    engine = create_async_engine(url, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    async with _engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            await session.close()
            if transaction.is_active:
                await transaction.rollback()


@pytest_asyncio.fixture(loop_scope="session")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --- Factory fixtures ---

CategoryFactory = Callable[..., Awaitable[Category]]
FoodFactory = Callable[..., Awaitable[Food]]
AddOnFactory = Callable[..., Awaitable[AddOn]]


@pytest_asyncio.fixture(loop_scope="session")
async def make_category(db_session: AsyncSession) -> CategoryFactory:
    counter = itertools.count(1)

    async def _make(**kwargs: Any) -> Category:
        n = next(counter)
        data: dict[str, Any] = {
            "name": f"Category {n}",
            "slug": f"category-{n}",
            "display_order": n,
            "is_active": True,
        }
        data.update(kwargs)
        category = Category(**data)
        db_session.add(category)
        await db_session.flush()
        return category

    return _make


@pytest_asyncio.fixture(loop_scope="session")
async def make_food(db_session: AsyncSession, make_category: CategoryFactory) -> FoodFactory:
    counter = itertools.count(1)

    async def _make(**kwargs: Any) -> Food:
        n = next(counter)
        category = kwargs.pop("category", None)
        if category is None and "category_id" not in kwargs:
            category = await make_category()
        data: dict[str, Any] = {
            "name": f"Food {n}",
            "price": Decimal("300.00"),
            "min_order_quantity": 1,
            "is_available": True,
            "is_single_serving": True,
            "requires_advance_order": True,
        }
        if category is not None:
            data["category_id"] = category.id
        data.update(kwargs)
        food = Food(**data)
        db_session.add(food)
        await db_session.flush()
        return food

    return _make


@pytest_asyncio.fixture(loop_scope="session")
async def owner_user(db_session: AsyncSession) -> AdminUser:
    user = AdminUser(
        name="Test Owner",
        email="owner@test.local",
        hashed_password=hash_password("password123"),
        role=AdminRole.owner,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture(loop_scope="session")
async def staff_user(db_session: AsyncSession) -> AdminUser:
    user = AdminUser(
        name="Test Staff",
        email="staff@test.local",
        hashed_password=hash_password("password123"),
        role=AdminRole.staff,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


def _auth_headers(user: AdminUser) -> dict[str, str]:
    token = create_access_token(user.id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


async def _authed_client(
    db_session: AsyncSession, user: AdminUser
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    headers = _auth_headers(user)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=headers
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(loop_scope="session")
async def owner_client(
    db_session: AsyncSession, owner_user: AdminUser
) -> AsyncGenerator[AsyncClient, None]:
    async for c in _authed_client(db_session, owner_user):
        yield c


@pytest_asyncio.fixture(loop_scope="session")
async def staff_client(
    db_session: AsyncSession, staff_user: AdminUser
) -> AsyncGenerator[AsyncClient, None]:
    async for c in _authed_client(db_session, staff_user):
        yield c


OrderFactory = Callable[..., Awaitable[Order]]


@pytest_asyncio.fixture(loop_scope="session")
async def make_order(db_session: AsyncSession) -> OrderFactory:
    counter = itertools.count(1)

    async def _make(**kwargs: Any) -> Order:
        n = next(counter)
        data: dict[str, Any] = {
            "invoice_number": f"DD-TEST-{n:04d}",
            "lookup_token": f"tok{n:04d}",
            "customer_name": f"Customer {n}",
            "customer_phone": "03001234567",
            "order_source": OrderSource.catalog,
            "requested_date": date.today() + timedelta(days=1),
            "is_custom": False,
        }
        data.update(kwargs)
        order = Order(**data)
        db_session.add(order)
        await db_session.flush()
        return order

    return _make


@pytest_asyncio.fixture(loop_scope="session")
async def make_addon(db_session: AsyncSession) -> AddOnFactory:
    counter = itertools.count(1)

    async def _make(**kwargs: Any) -> AddOn:
        n = next(counter)
        data: dict[str, Any] = {
            "name": f"Add-on {n}",
            "price": Decimal("50.00"),
            "is_available": True,
            "is_global": False,
        }
        data.update(kwargs)
        addon = AddOn(**data)
        db_session.add(addon)
        await db_session.flush()
        return addon

    return _make
