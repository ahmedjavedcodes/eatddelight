# Daughter's Delight — Backend

FastAPI service for the Daughter's Delight (`@eatddelight`) home-kitchen ordering site.
See [`CLAUDE.md`](CLAUDE.md) for the full architecture and [`specs/`](specs/) for the
spec-driven docs. Build plans live in [`../plans/backend/`](../plans/backend/).

## Stack

FastAPI (async) · SQLAlchemy 2.x async + asyncpg · PostgreSQL 18 · Pydantic v2 ·
Alembic · pytest · ruff · mypy. Environment: `venv` + `pip` (no Docker, no `uv`).

## Prerequisites

- Python 3.12+ (3.13 present via the `py` launcher).
- PostgreSQL 18 running locally (service `postgresql-x64-18`, `localhost:5432`),
  superuser role `postgres`. `psql` lives at `C:\Program Files\PostgreSQL\18\bin`.

## Setup

```powershell
# 1. Databases (once) — pgAdmin, or psql:
$psql = "C:\Program Files\PostgreSQL\18\bin\psql.exe"
& $psql -U postgres -h localhost -d postgres -c "CREATE DATABASE eatddelight OWNER postgres;"
& $psql -U postgres -h localhost -d postgres -c "CREATE DATABASE eatddelight_test OWNER postgres;"

# 2. Virtualenv + deps
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# 3. Env
Copy-Item .env.example .env
#   then edit .env: set the postgres password in DATABASE_URL / TEST_DATABASE_URL,
#   and set SECRET_KEY to a random 32+ byte string.

# 4. Migrations (no-op until plan 02 adds models)
alembic upgrade head
```

## Run

```powershell
uvicorn app.main:app --reload
# http://127.0.0.1:8000/api/v1/health  -> {"status":"ok"}
# http://127.0.0.1:8000/docs
```

## Checks

```powershell
ruff check .
ruff format --check .
mypy app
pytest
```

## Layout

```
app/
  api/v1/         routers (endpoints/, admin/, deps.py, router.py)
  core/           config.py, errors.py, security.py (plan 05)
  db/             base.py, session.py
  models/         SQLAlchemy models (plan 02)
  schemas/        Pydantic models (plans 03+)
  services/       business logic (plans 03+)
  main.py         create_app() factory
alembic/          migrations
scripts/          seed_menu.py (plan 02)
tests/            conftest.py + test_*.py
```
