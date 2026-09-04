# 00 — Backend Overview & Conventions

**Purpose:** Shared context, conventions, project structure, and cross-cutting concerns that every other plan file in this folder builds on. Read this first.

**Implements from `backend/CLAUDE.md`:** §1–§3 (context/stack/scope), §10 (auth model, shared parts), §11 (structure), §12 (testing/lint/migrations), §13 phases 1 & 10 & 11, §14 (open questions).

**Prerequisites:** none.

**Definition of done for this doc:** the other five plans can be executed without re-reading CLAUDE.md for structure, naming, error shape, config, or the hardening checklist.

---

## 1. Business context (recap)

Daughter's Delight (`@eatddelight`, phone `0312-2252915`) is a single home kitchen. Customers browse a website, build a cart or submit a bespoke request, and check out **without an account and without online payment** — checkout produces a plain order summary plus a pre-filled WhatsApp message to the owner and a downloadable PDF invoice. The owner and owner-added staff manage the menu through an admin panel.

Two product lines, both requiring ≥ 1 day advance ordering:

- **Menu of the Day** — one fixed dish per weekday (Mon–Fri), single-serving, min qty 1.
- **Full Menu (à la carte)** — catalog grouped into categories, min qty 3 per item, subject to availability.

## 2. Scope / non-goals

**In scope:** menu/catalog APIs, cart, favourites, orders + PDF invoice + WhatsApp handoff, custom order requests, admin CRUD with role-based permissions, contact form capture, site settings.

**Out of scope (do not build unless the client later asks):** customer accounts/login, online payments, SMS/email notifications, real-time order tracking, delivery logistics, multi-tenant support.

## 3. Tech stack (locked)

| Concern | Choice |
|---|---|
| Framework | FastAPI (async) |
| ORM | SQLAlchemy 2.x async + `asyncpg` |
| DB | PostgreSQL 16 |
| Schemas/config | Pydantic v2 + `pydantic-settings` |
| Migrations | Alembic (async template) |
| Testing | pytest, pytest-asyncio, httpx `AsyncClient` + `ASGITransport`, disposable Postgres test DB |
| Lint/format | ruff (lint + format) |
| Types | mypy (strict on `app/`, relaxed on `tests/`) |
| Admin auth | JWT access + refresh; passwords via `passlib[bcrypt]` (argon2 acceptable) |
| PDF | WeasyPrint (HTML→PDF); reportlab fallback if system deps missing |
| Env/deps | **`venv` + `pip`** (`pip install -e ".[dev]"`; deps declared in `pyproject.toml`) — chosen for this machine, not `uv`/poetry |
| Local infra | Locally-installed PostgreSQL (pgAdmin / `psql`) — **no Docker** |

## 4. Project structure (from §11, annotated with owning plan)

```
backend/
  app/
    api/
      v1/
        endpoints/        # public routers            -> 03, 04
          settings.py                                 # 03
          categories.py                               # 03
          menu.py                                     # 03 (/menu, /weekly-menu)
          foods.py                                    # 03
          cart.py                                     # 03
          favourites.py                               # 03
          orders.py                                   # 04
          contact.py                                  # 05 (public POST lives here)
        admin/            # admin routers             -> 05
          auth.py
          categories.py
          foods.py
          addons.py
          orders.py
          staff.py
          settings.py
          contact_messages.py
        deps.py           # db session, session-token, current admin, require_role  -> 01 (stubs) / 05 (auth)
        router.py         # aggregates v1 routers under /api/v1                      -> 01
    core/
      config.py           # pydantic-settings Settings + get_settings()             -> 01
      security.py         # password hashing + JWT encode/decode                    -> 05
      errors.py           # domain exception types + FastAPI handlers               -> 01 (shell) / filled 03-05
    db/
      base.py             # DeclarativeBase, TimestampMixin, metadata               -> 01
      session.py          # async engine, sessionmaker, get_db()                    -> 01
    models/               # one module per aggregate                                -> 02
    schemas/              # Pydantic request/response models                        -> 03, 04, 05
    services/             # business logic                                          -> 03, 04, 05
      clock.py            # now_pk(), earliest_requested_date()                     -> 04 (defined), used 03+04
      whatsapp.py                                                                   # 04
      invoice.py                                                                    # 04
    templates/
      invoice.html        # Jinja2 invoice template                                 -> 04
    main.py               # create_app() factory                                    -> 01
  alembic/
    env.py                # async config, target_metadata = Base.metadata           -> 01
    versions/                                                                       # 02+
  scripts/
    seed_menu.py          # §5 seed data + SiteSettings + owner account             -> 02
  tests/
    conftest.py           # test DB + AsyncClient + factory fixtures                -> 01
    test_health.py                                                                  # 01
    test_models.py  test_seed.py                                                    # 02
    test_menu.py  test_cart.py  test_favourites.py                                  # 03
    test_orders.py  test_invoice.py                                                 # 04
    test_admin_auth.py  test_admin_permissions.py  test_admin_crud.py  test_contact.py  # 05
  pyproject.toml  alembic.ini  .env.example  README.md      # no docker-compose.yml — local Postgres
```

## 5. Plan dependency order

```
01 (scaffolding)
   └── 02 (models + migrations + seed)
          ├── 03 (public catalog / cart / favourites)
          │      └── 04 (orders + invoicing)   # needs cart from 03
          └── 05 (admin auth / CRUD / contact) # needs owner seed from 02, order model from 02, admin order mgmt touches 04's order
```

Build strictly in this order. Each plan's "Definition of done" (its tests green + `ruff`/`mypy` clean for that slice) is the gate to start the next.

## 6. Cross-cutting conventions (every plan follows these)

### 6.1 Async everywhere
All routes `async def`; all DB access via `AsyncSession`. No sync SQLAlchemy sessions, no blocking IO in request path (WeasyPrint runs in a threadpool via `run_in_threadpool` / `asyncio.to_thread`).

### 6.2 Layering
- **Routers** (`app/api/v1/...`): parse/validate input, resolve dependencies (db, session token, current admin, role), call one service function, serialize the result. No business logic, no multi-step DB orchestration.
- **Services** (`app/services/...`): all business rules, transactions, price snapshotting, invoice numbering, WhatsApp/PDF building. Take an `AsyncSession` + plain args, return ORM objects or dataclasses.
- **DB constraints** are a backstop, not the primary defense — every rule in CLAUDE.md §7 is enforced in a service or Pydantic validator, with a DB constraint behind it where cheap.

### 6.3 Pydantic v2
- Separate `XCreate` / `XUpdate` / `XRead` schema classes per resource; `XRead` sets `model_config = ConfigDict(from_attributes=True)`.
- Use `Annotated[...]` with `Field` constraints; validators via `@field_validator` / `@model_validator(mode="after")`.
- Money fields typed `Decimal` (see 6.4). Dates as `datetime.date`, timestamps as timezone-aware `datetime`.

### 6.4 Money
`Numeric(8, 2)` columns, `Decimal` in Python, **never `float`**. Currency is PKR throughout; no multi-currency. `OrderItem.unit_price` and `order_item_addons.unit_price` are **snapshots** copied from the live `Food`/`AddOn` price at order-creation time and never recomputed (CLAUDE.md §7 rule 5). Cart line prices are computed live (not snapshotted).

### 6.5 Time & advance-ordering
Business timezone is `Asia/Karachi`. `app/services/clock.py` centralizes it so tests can monkeypatch:

```python
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

PK_TZ = ZoneInfo("Asia/Karachi")

def now_pk() -> datetime:
    return datetime.now(tz=PK_TZ)

def today_pk() -> date:
    return now_pk().date()

def earliest_requested_date() -> date:
    """Rule 1: at least one day in advance, in Asia/Karachi."""
    return today_pk() + timedelta(days=1)
```

All date validation imports from here — never call `datetime.now()` directly in services.

### 6.6 Error shape
One consistent JSON body for every handled error:

```json
{ "detail": "human message", "code": "STABLE_SNAKE_CODE" }
```

`app/core/errors.py` defines a base `DomainError(Exception)` with `status_code: int`, `code: str`, `detail: str`, plus concrete subclasses. `create_app()` registers one exception handler that renders any `DomainError` into the shape above, and a handler that reshapes FastAPI's `RequestValidationError` / `HTTPException` into the same shape.

| Exception | HTTP | `code` | Raised in plan |
|---|---|---|---|
| `MinQuantityError` | 422 | `min_quantity` | 03, 04 |
| `UnavailableItemError` | 409 | `item_unavailable` | 03, 04 |
| `AdvanceOrderError` | 422 | `advance_order_required` | 04 |
| `DayOfWeekMismatchError` | 422 | `day_of_week_mismatch` | 04 |
| `EmptyOrderError` | 422 | `empty_order` | 04 |
| `InvalidLookupToken` → return 404 | 404 | `not_found` | 04 |
| `AuthError` | 401 | `unauthorized` | 05 |
| `PermissionError` (custom) | 403 | `forbidden` | 05 |
| `CategoryInUseError` | 409 | `category_in_use` | 05 |

### 6.7 Session token
Anonymous customers are identified only by an opaque `X-Session-Token` header (a UUID the frontend generates and stores). Dependency in `app/api/v1/deps.py`:

```python
async def get_session_token(x_session_token: Annotated[str, Header()]) -> str:
    # no validation beyond "present and non-empty" — it is a bucket key, not auth
```

No expiry, no signing, no server-side issuance. Missing header on a cart/favourites/order request → 422 via the normal validation path.

### 6.8 API surface
Everything under `/api/v1`. `app/api/v1/router.py` includes every sub-router with an OpenAPI `tags=[...]` value: `settings`, `catalog`, `cart`, `favourites`, `orders`, `contact`, `admin:auth`, `admin:catalog`, `admin:orders`, `admin:staff`, `admin:settings`, `admin:contact`.

### 6.9 Config & secrets
`app/core/config.py` exposes a single `Settings(BaseSettings)` (`.env` file, env vars). `get_settings()` is `@lru_cache`d and injected as a dependency. Secrets (`SECRET_KEY`, `OWNER_PASSWORD`, DB password) are never committed — `.env.example` carries placeholder values only.

## 7. Environment variables (`.env.example` contents)

```dotenv
# --- Database (local PostgreSQL 18 server; manage via pgAdmin or psql) ---
# Superuser role: postgres. Fill in the real password. Port 5432.
DATABASE_URL=postgresql+asyncpg://postgres:CHANGE_ME@localhost:5432/eatddelight
TEST_DATABASE_URL=postgresql+asyncpg://postgres:CHANGE_ME@localhost:5432/eatddelight_test

# --- App ---
APP_ENV=local                     # local | test | production
TZ=Asia/Karachi
API_V1_PREFIX=/api/v1
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# --- Auth (admin only) ---
SECRET_KEY=change-me-32-bytes-min
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
JWT_ALGORITHM=HS256

# --- Owner bootstrap (seeded once) ---
OWNER_EMAIL=owner@example.com
OWNER_PASSWORD=change-me
OWNER_NAME=Owner

# --- Business fallback (SiteSettings row is source of truth once seeded) ---
WHATSAPP_NUMBER=923122252915

# --- Rate limiting ---
RATE_LIMIT_PUBLIC_WRITE=10/minute
```

## 8. Testing conventions (§12)

- pytest + pytest-asyncio (`asyncio_mode = "auto"`).
- A dedicated Postgres test database on the local server (`TEST_DATABASE_URL` → `eatddelight_test`, owner `postgres`). Pre-create it once in pgAdmin, or let `conftest.py` create it if missing. The **schema** is rebuilt per session (`alembic upgrade head` or `Base.metadata.create_all`); the database itself can persist between runs.
- Per-test isolation via a nested transaction / SAVEPOINT rolled back in a fixture teardown — tests never see each other's rows.
- HTTP tests use `httpx.AsyncClient(transport=ASGITransport(app=app))` with the `get_db` dependency overridden to the test session.
- Factory fixtures in `conftest.py` for `Category`, `Food`, `AddOn`, `AdminUser(owner)`, `AdminUser(staff)`, and an authed-client fixture per role.
- Coverage targets called out per plan; the non-negotiables: every §7 business rule, the Monday-ordered-on-Monday date edge case, staff-403-on-delete, invoice-number uniqueness, WhatsApp message formatting.

## 9. Migrations conventions (§12)

- Every model change ships an Alembic revision from `alembic revision --autogenerate -m "..."`, **hand-reviewed before commit** — autogenerate misses enum value changes, renames, `server_default` changes, and check constraints.
- Never mutate the schema outside a migration.
- Enum types: create explicitly in the migration (`sa.Enum(..., name="order_status")`) and manage value additions manually.

## 10. Lint / pre-commit (§12)

- `ruff check` + `ruff format --check` + `mypy app` must pass before each plan is "done".
- `.pre-commit-config.yaml` runs ruff (lint+format), mypy, and `pytest -q` on push.

## 11. Phase 10–11 — Hardening & release checklist

Do this pass only after plans 01–05 are all green. Tracked here so it is not forgotten.

- [ ] **CORS**: replace the dev origin list with the real deployed frontend origin(s); credentials off (no cookies used).
- [ ] **Rate limiting** on public write endpoints — `POST /cart`, `POST/PATCH/DELETE /cart/items/*`, `POST /orders`, `POST /favourites`, `POST /contact` — via `slowapi` (or reverse-proxy limits). `RATE_LIMIT_PUBLIC_WRITE` from env. These have no auth and are a cheap abuse vector.
- [ ] **Structured logging**: JSON logs, request id middleware, log every order creation and admin mutation with actor + entity id. No secrets / no full card-style data (there is none, but no phone numbers in logs beyond debug level).
- [ ] **Consistent error shape** (§6.6) applied to *all* paths incl. 404/405/500; no raw stack traces in responses.
- [ ] **OpenAPI cleanup**: `response_model` on every route, `tags` on every router, `summary`/`description`, at least one `examples` per request body, `operation_id`s stable for the frontend codegen.
- [ ] **Security headers** middleware (`X-Content-Type-Options`, `Referrer-Policy`, basic `Content-Security-Policy` for the docs).
- [ ] **DB**: connection pool sizing for the deploy target; `pool_pre_ping=True`.
- [ ] **Full suite green**, `ruff` + `mypy` clean, `alembic upgrade head` from empty works, `seed_menu.py` idempotent.
- [ ] **Seed-data typo review against the flyer images** — decide *with the client* whether to correct or keep verbatim: `Khauasay` vs `Khousay`, `Ceasar` vs `Caesar`, `Alo Goshat`/`Alo Palak` vs `Aloo`, `Raps` vs `Wraps`, `Sizler` vs `Sizzler`. Whatever is decided, `name` (display) and `slug` must stay stable afterward.

## 12. Open questions for the client (CLAUDE.md §14 — flag, do not silently guess)

1. **Staff & `SiteSettings`** — may `staff` edit About/Contact/social copy, or is `PUT /admin/settings` owner-only? (Plan 05 defaults to **owner-only**; make the role check a one-line change.)
2. **Custom order structured input** — beyond free-text `custom_description`, does the client want structured fields (servings count, budget range, occasion, event date)? (Plan 04 currently: free text + optional catalog items only.)
3. **Order status set** — confirm `pending → confirmed → preparing → ready → delivered` (+ `cancelled`) matches how the kitchen actually tracks an order. (Plan 02 encodes exactly this enum; plan 05 enforces forward-only transitions + `cancelled` from any non-terminal state.)

## 13. Assumptions being made (flag if any matter to the client)

- **Owner-only delete extended** from "food items" to categories and add-ons too, for consistency (CLAUDE.md §1 note). Staff can still create/update all three.
- **"Menu of the Day" is a normal `Category`** (slug `menu-of-the-day`), satisfying the required one-Category-has-many-Foods relationship; `/weekly-menu` is a distinct query, not a separate table or a `kind` flag (CLAUDE.md §6 note).
- **`Order.lookup_token`** (short random string) is added beyond §4's field list so `GET /orders/{id}` and the invoice endpoint can require `?token=` and stay non-enumerable.
- **`Order.total` is nullable** so `custom_request` orders can exist unpriced until the owner quotes them (§7 rule 7, §9).
- **Cart is cleared** after a successful order created from it.
- **Deliberate duplicate dishes** ("Alfredo Pasta" daily 600 vs House Favourites 550; "Special Khousay" Wednesday special vs Khousay category) are modelled as **separate `Food` rows** — no dedupe.
- **Local PostgreSQL instead of docker-compose** (deviation from CLAUDE.md §2, per user instruction): dev + test run against the machine's installed **PostgreSQL 18** (service `postgresql-x64-18`, superuser `postgres`), databases `eatddelight` + `eatddelight_test`, managed with pgAdmin / `psql`. No `docker-compose.yml` in the repo.
- **`venv` + `pip` instead of `uv`** (deviation from CLAUDE.md §2 / earlier plan, per user instruction): `uv` is not installed on this machine. Environment is a project `.venv` (Python 3.13 via the `py` launcher); dependencies live in `pyproject.toml` and install with `pip install -e ".[dev]"`. No `uv.lock`.
