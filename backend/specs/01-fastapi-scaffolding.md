# Spec: FastAPI Scaffolding

> Scope: Phase 1 of the backend build — an empty-but-runnable FastAPI service with the shared plumbing every later slice imports. Source plan: `plans/backend/01-fastapi-scaffolding.md`. Conventions: `plans/backend/00-overview.md` / `backend/specs/00-overview.md`.
>
> Machine-specific decisions for this run: **`venv` + `pip`** (no `uv`); **local PostgreSQL 18** (service `postgresql-x64-18`, superuser `postgres`, databases `eatddelight` + `eatddelight_test`), no Docker.

## Problem Statement

`backend/` contains only `CLAUDE.md` and the plan set — nothing executable. Every feature slice (catalog, cart, orders, invoicing, admin) imports the same foundation: a `create_app()` factory, `Settings` config, an async DB session dependency, the error envelope, the `/api/v1` router, and a pytest harness that can reach the local Postgres. Until that exists, plan 02 has nowhere to attach models, there is no way to run a single test, and each contributor would improvise a different bootstrap — the exact divergence the plan set exists to prevent. This plan is the gate for the whole backend: it moves the repo to build state `scaffolded`.

## Functional Requirements

1. **`pyproject.toml`** declaring runtime deps and a `dev` optional-dependencies group, plus `ruff` / `mypy` / `pytest` tool config; installs into a project `.venv` with `pip install -e ".[dev]"`.
2. **`app/core/config.py`** — `Settings(BaseSettings)` reading `.env`; `@lru_cache get_settings()`; `cors_origins` accepts a comma-separated string as well as JSON.
3. **`app/db/base.py`** — `Base(DeclarativeBase)` carrying a `MetaData` with the `ix_/uq_/ck_/fk_/pk_` naming convention, and a `TimestampMixin` (`created_at`, `updated_at`).
4. **`app/db/session.py`** — async engine from `DATABASE_URL` (`pool_pre_ping=True`), `async_sessionmaker(expire_on_commit=False)`, and a `get_db()` dependency that yields an `AsyncSession`, commits on success and rolls back on exception.
5. **`app/core/errors.py`** — `DomainError` base (`status_code`, `code`, `detail`) and three exception handlers (`DomainError`, Starlette `HTTPException`, `RequestValidationError`) that all emit `{"detail": …, "code": …}`.
6. **`app/api/v1/deps.py`** — re-export `get_db`; `get_session_token` reading `X-Session-Token` (`Header(min_length=1)`), returned verbatim.
7. **`app/api/v1/router.py`** + **`app/api/v1/endpoints/health.py`** — `GET /api/v1/health` → `{"status": "ok"}`, tagged `health`.
8. **`app/main.py`** — `create_app()` factory wiring CORS from `settings.cors_origins`, the three handlers, the v1 router under `settings.api_v1_prefix`, and a lifespan that disposes the engine on shutdown; module-level `app = create_app()`.
9. **Alembic (async)** — `alembic init -t async alembic`; `env.py` bound to `Base.metadata` (imports `app.db.base` + `app.models` once it exists) and `get_settings().database_url`; `alembic.ini` with no hardcoded URL; `alembic upgrade head` runs clean with zero revisions.
10. **`tests/conftest.py`** — test engine on `TEST_DATABASE_URL` (creates `eatddelight_test` if missing); session-scoped schema build (`Base.metadata.create_all` for now); function-scoped `db_session` in a SAVEPOINT rolled back on teardown; function-scoped `client` = `AsyncClient(transport=ASGITransport(app=create_app()))` with `get_db` overridden; stubbed factory fixtures (`make_category`, `make_food`, `make_addon`, `owner_user`, `staff_user`, `owner_client`, `staff_client`).
11. **`tests/test_health.py`** — asserts `GET /api/v1/health` → `200 {"status":"ok"}`.
12. **Repo hygiene** — `.pre-commit-config.yaml` (ruff, ruff-format, mypy, `pytest -q` on push); `.gitignore` (`.venv/`, `.env`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `*.egg-info/`); `README.md` with the run steps.
13. **Databases** — `eatddelight` and `eatddelight_test` created on the PG18 server, owner `postgres`.
14. **Env files** — `.env.example` committed with placeholders; a local `.env` (gitignored) holding the real `DATABASE_URL` / `TEST_DATABASE_URL` and dev-only `SECRET_KEY` / `OWNER_EMAIL` / `OWNER_PASSWORD`.

**Out of scope (deferred, not dropped):** any domain model or table (plan 02); any business endpoint; rate limiting, security headers, structured logging (Phase 10–11); a Dockerfile; CI configuration; a dependency lockfile.

## Behaviour

The feature has no runtime end-user flow; it moves the repo from **nothing runnable** to build state **`scaffolded`**.

**Primary flow (one-time, developer):**

1. Create `eatddelight` and `eatddelight_test` on the local PG18 server — pgAdmin, or `& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -d postgres -c "CREATE DATABASE eatddelight OWNER postgres;"` (repeat for `_test`).
2. `py -m venv .venv`; activate (`.venv\Scripts\Activate.ps1` / `source .venv/Scripts/activate`); `pip install -e ".[dev]"`.
3. Copy `.env.example` → `.env`; set `DATABASE_URL` / `TEST_DATABASE_URL` to `postgresql+asyncpg://postgres:<password>@localhost:5432/eatddelight[_test]`; set a dev `SECRET_KEY`.
4. `alembic upgrade head` → exits 0, applies nothing (no revisions yet).
5. `pytest` → `tests/test_health.py` green.
6. `ruff check .` + `ruff format --check .` + `mypy app` → all clean.
7. `uvicorn app.main:app --reload` → `GET /api/v1/health` returns `{"status":"ok"}`; `/docs` renders with exactly one route under the `health` tag.
8. Stage **`backend/` only**, commit, create a `master` branch from that commit, push `master` to `origin`.

There are no roles or sub-states — the app exposes one public, unauthenticated route.

## Constraints

- Inherits `backend/specs/00-overview.md` Constraints, with two machine-specific deviations already folded in there: **`venv` + `pip`** (deps in `pyproject.toml`, `pip install -e ".[dev]"`, no `uv`/poetry, no lockfile) and **local PostgreSQL 18** (no Docker), superuser `postgres`, DB `eatddelight` / `eatddelight_test`.
- Python 3.12+ — 3.13 is installed via the `py` launcher. `python` / `pip` exist only inside the activated `.venv`.
- `psql` / `pg_isready` are **not on PATH**; use `C:\Program Files\PostgreSQL\18\bin\`.
- `pg_hba.conf` enforces `scram-sha-256` — every DB connection needs the `postgres` password.
- Async everywhere; `{"detail","code"}` error envelope; the `Decimal` money rule and `clock.py` are not exercised here but the base classes must not preclude them.
- `weasyprint` is a declared dependency but is **not imported** by the health app; a missing Windows GTK/Pango runtime must not block scaffolding (the import is deferred to plan 04).
- Secrets never committed: `.env` is gitignored; `.env.example` is placeholders only.
- The plan's commit contains **`backend/**` only** — not `plans/`, not `.claude/`.

## Edge Cases and Error Handling

| Trigger | Expected Response |
|---|---|
| `.env` missing `DATABASE_URL` or `SECRET_KEY` | `get_settings()` raises a Pydantic `ValidationError` naming the field; app and tests fail fast, no boot. |
| `DATABASE_URL` wrong password / non-existent DB | `alembic upgrade head` and app startup fail with a clear `asyncpg` `InvalidPasswordError` / `InvalidCatalogName`; `README` documents the fix. |
| `eatddelight_test` absent when tests start | `conftest.py` connects to the `postgres` maintenance DB and issues `CREATE DATABASE eatddelight_test`; if that fails on perms, the test errors with "create it in pgAdmin". |
| `psql` called without a full path | Not found on PATH; scripts and `README` use the `C:\Program Files\PostgreSQL\18\bin\` path. |
| `import weasyprint` fails (missing GTK libs) | Scaffolding still runs — the health app never imports it; `pip install` itself does not fail. Flagged for plan 04. |
| `cors_origins` supplied as `"http://a,http://b"` | `field_validator(mode="before")` splits on comma → `["http://a","http://b"]`; empty string → `[]`. |
| A handler raises a `DomainError` subclass | Response is `{"detail": …, "code": …}` with the subclass's `status_code`; no traceback. (Structural here; exercised by later plans.) |
| Request to an unknown route | FastAPI 404 reshaped by the `HTTPException` handler to `{"detail": …, "code": "http_error"}`. |
| `mypy app` finds an untyped/incomplete def | Fails the gate (`strict = true`); all scaffolding code is fully annotated. |
| `alembic upgrade head` with zero revisions | Exits 0 as a no-op — must not error. |
| A commit would include `.env` | `.gitignore` lists `.env`; `git status --porcelain backend/` is checked before committing and shows no `.env`. |
| `git push` of `master` rejected (already exists / protected) | Stop and report; **no `--force`**. `master` is new, so this is not expected. |
| `pip install -e .` needs a build backend | `pyproject.toml` declares `hatchling`; `[tool.hatch.build.targets.wheel] packages = ["app"]`. |

## Acceptance Criteria

- [ ] Given a fresh `.venv`, when `pip install -e ".[dev]"` runs, then it completes and `python -c "import app.main"` succeeds.
- [ ] Given `.env` with a valid `DATABASE_URL` and `SECRET_KEY`, when `alembic upgrade head` runs, then it exits 0 and applies no revisions.
- [ ] Given `SECRET_KEY` removed from `.env`, when `pytest` or `uvicorn app.main:app` starts, then a Pydantic `ValidationError` naming `secret_key` is raised and the process exits non-zero.
- [ ] `pytest` runs `tests/test_health.py` green against `eatddelight_test` via the `AsyncClient` + `ASGITransport` fixture.
- [ ] `ruff check .`, `ruff format --check .`, and `mypy app` each exit 0.
- [ ] With `uvicorn app.main:app` running, `GET /api/v1/health` returns `200 {"status":"ok"}` and `/docs` shows exactly one route under a `health` tag.
- [ ] `get_db()` commits after a successful request and rolls back when the handler raises (fixture-level or dummy-route test).
- [ ] `get_settings()` returns the same instance across calls; `cors_origins` parses `"http://a,http://b"` into a 2-element list.
- [ ] `.gitignore` excludes `.venv/`, `.env`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`; `git status --porcelain backend/` shows no `.env`.
- [ ] A `master` branch exists containing a single commit that adds **only** `backend/**` (no `plans/`, no `.claude/`), and `master` is pushed to `origin`.

**Traceability:** every FR maps to at least one acceptance criterion (FR1→install; FR2→settings/CORS; FR3–4→`import` + `get_db`; FR5→`DomainError`/unknown-route rows + handlers wired in `create_app`; FR6→covered by `import` + health route; FR7→`/docs` route criterion; FR8→`uvicorn` criterion; FR9→`alembic upgrade head` criterion; FR10–11→`pytest` criterion; FR12→`.gitignore` + ruff/mypy criteria; FR13→"green against `eatddelight_test`"; FR14→the two `.env` criteria; git target→`master` criterion). Edge cases without a dedicated criterion are marked "structural / exercised by later plans".
