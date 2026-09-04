"""Shared test fixtures.

- A dedicated Postgres test database (``TEST_DATABASE_URL`` -> ``eatddelight_test``),
  created if missing, schema rebuilt once per session.
- Per-test isolation via a SAVEPOINT that is rolled back on teardown.
- An ``httpx.AsyncClient`` bound to the ASGI app with ``get_db`` overridden.

Factory fixtures are stubbed here and fleshed out by later plans.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Iterator

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.v1.deps import get_db
from app.core.config import get_settings
from app.db.base import Base
from app.main import create_app

# Import model modules here once plan 02 adds them so Base.metadata is complete:
#   import app.models


def _test_database_url() -> str:
    settings = get_settings()
    url = settings.test_database_url or settings.database_url
    if url == settings.database_url:
        raise RuntimeError(
            "TEST_DATABASE_URL is not set; refusing to run the test suite against the "
            "development database. Set it in .env (e.g. .../eatddelight_test)."
        )
    return url


async def _ensure_database(async_url: str) -> None:
    """Create the target database if it does not exist yet."""
    url = make_url(async_url)
    db_name = url.database
    assert db_name is not None
    admin_dsn = f"postgresql://{url.username}:{url.password}@{url.host}:{url.port or 5432}/postgres"
    conn = await asyncpg.connect(admin_dsn)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await conn.close()


async def _reset_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture(scope="session")
def _engine() -> Iterator[AsyncEngine]:
    url = _test_database_url()
    asyncio.run(_ensure_database(url))
    engine = create_async_engine(url, poolclass=NullPool)
    asyncio.run(_reset_schema(engine))
    yield engine
    asyncio.run(engine.dispose())


@pytest_asyncio.fixture
async def db_session(_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    connection: AsyncConnection = await _engine.connect()
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
        await transaction.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --- Factory fixtures (stubs; filled in by plans 02+) ---


@pytest.fixture
def make_category() -> None:  # pragma: no cover - stub
    raise NotImplementedError("Defined in plan 02.")


@pytest.fixture
def make_food() -> None:  # pragma: no cover - stub
    raise NotImplementedError("Defined in plan 02.")


@pytest.fixture
def make_addon() -> None:  # pragma: no cover - stub
    raise NotImplementedError("Defined in plan 02.")
