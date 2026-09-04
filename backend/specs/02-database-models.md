# Spec: Database Models, Migrations & Seed

> Scope: Phase 2 of the backend build — every SQLAlchemy model, the enum types, all constraints, two hand-reviewed Alembic revisions, a minimal password-hashing helper, and an idempotent seed script for the flyer menu. Source plan: `plans/backend/02-database-models.md`. Conventions: `backend/specs/00-overview.md`.
>
> **Incorporates two decisions from the `/spec 00` interview that revise the source plan:** `OrderStatus` is `pending → confirmed → completed` (+ `cancelled`), not the plan's 6-value set; and `Order` gains four optional structured custom-order fields. `plans/backend/02-database-models.md` must be edited to match (see the last acceptance criterion).

## Problem Statement

After plan 01 the service runs but owns **zero domain tables** — `Base.metadata` is empty, `alembic upgrade head` is a no-op, and plans 03–05 have nothing to attach endpoints to. The whole domain (Menu-of-the-Day + à la carte catalog, cart, favourites, orders, PDF-invoice data, admin users, site settings, contact inbox) needs its tables, relationships and constraints defined **once, correctly**: a wrong column type, a missing `ON DELETE` rule, or a snapshot column left out here becomes a migration rewrite and lost order history later. The menu itself — 11 categories and 42 dishes transcribed from the two flyers — must be loadable **repeatably** so every dev machine, CI run and the eventual production DB start from an identical catalog. This is a one-time foundation, but everything downstream reads from it; until it exists, plans 03–05 are blocked.

## Functional Requirements

1. **Enums** (`app/models/enums.py`), mapped as named PostgreSQL types: `DayOfWeek` (`mon,tue,wed,thu,fri`), `OrderSource` (`catalog,custom_request`), `OrderStatus` (`pending,confirmed,completed,cancelled`), `AdminRole` (`owner,staff`).
2. **Models**, one module per aggregate under `app/models/`, all inheriting `Base` and `TimestampMixin` (except pure association tables and `Favourite`/`SiteSettings`/`ContactMessage`/`AdminUser` where the field list says otherwise): `Category`; `Food` + `food_addons` table; `AddOn`; `Cart`, `CartItem`, `CartItemAddon`; `Favourite`; `Order`, `OrderItem`, `OrderItemAddon`; `AdminUser`; `SiteSettings`; `ContactMessage`.
3. **`app/models/__init__.py`** importing every model module so `Base.metadata` is complete (Alembic autogenerate + the test fixtures rely on it). The guarded `try: import app.models` in `alembic/env.py` (added in plan 01) now resolves.
4. **Column sets** per CLAUDE.md §4 with the documented additions: `Order.lookup_token` (str 32, indexed); nullable `Order.subtotal` / `Order.total`; `OrderItem.food_name` and `OrderItemAddon.addon_name` snapshot strings; `OrderItemAddon` surrogate `id` PK + `UniqueConstraint(order_item_id, addon_id)`.
5. **Revised — structured custom-order fields:** `Order` gains nullable `servings` (int), `budget_range` (str 60), `occasion` (str 120), `event_date` (date). All optional; `custom_description` remains the only field required when `order_source = custom_request` (enforced in the service layer, plan 04).
6. **Revised — order status:** `OrderStatus` has exactly four values `pending, confirmed, completed, cancelled`.
7. **Constraints & indexes**, named by the `ix_/uq_/ck_/fk_/pk_` convention from plan 01:
   - unique: `categories.slug`, `orders.invoice_number`, `carts.session_token`, `favourites (session_token, food_id)`, `admin_users.email`, `order_item_addons (order_item_id, addon_id)`.
   - check: `foods.price > 0`, `foods.min_order_quantity >= 1`, `addons.price >= 0`, `quantity >= 1` on `cart_items` / `cart_item_addons` / `order_items` / `order_item_addons`, `site_settings.id = 1`.
   - FK `ON DELETE`: `foods.category_id` → **RESTRICT**; `order_items.food_id` and `order_item_addons.addon_id` → **SET NULL**; all cart/order child rows and `food_addons` → **CASCADE**; `favourites.food_id` → CASCADE.
   - indexes: `foods.category_id`, `foods.day_of_week`, `carts.session_token`, `favourites.session_token`, `orders.lookup_token`, `admin_users.email`.
8. **Types:** every monetary column `Numeric(8, 2)` mapped to `Decimal`; every timestamp timezone-aware; `Text` for long free-text (`about_text`, `custom_description`, `admin_notes`, `contact_messages.message`).
9. **Two hand-reviewed Alembic revisions:**
   - `0001_core_catalog` — the 4 enum types + `categories`, `foods`, `addons`, `food_addons`, `site_settings`, `admin_users`.
   - `0002_cart_orders_contact` — `carts`, `cart_items`, `cart_item_addons`, `favourites`, `orders`, `order_items`, `order_item_addons`, `contact_messages`.
   - Generated via `alembic revision --autogenerate`, then hand-edited (enum creation, `server_default`s, check constraints, `ondelete`, the `id = 1` CK). `upgrade head` from empty builds everything; `downgrade base` tears it all down including the enum types.
10. **`app/core/security.py`** — `hash_password(raw: str) -> str` and `verify_password(raw: str, hashed: str) -> bool` using `passlib[bcrypt]`. Plan 05 later adds JWT encode/decode to the same module.
11. **`scripts/seed_menu.py`** — an idempotent `async def seed(session)` that upserts, in order: `SiteSettings` (id=1, business/brand fields from CLAUDE.md §5, without clobbering admin-set `about_text`/`address`/`opening_hours`); exactly one `owner` `AdminUser` from `OWNER_EMAIL`/`OWNER_PASSWORD`/`OWNER_NAME` **only if no owner exists** (never rotates an existing password); 11 categories; 42 foods (5 daily specials with `day_of_week` set + 37 full-menu) transcribed verbatim from §5. Plus a `__main__` entrypoint that opens a session, runs `seed`, commits. **No `AddOn` rows** are seeded.
12. **`conftest.py` updates** — real `make_category` / `make_food` / `make_addon` factory fixtures; the session-scoped test schema is built by running **`alembic upgrade head`** (replacing `Base.metadata.create_all`), after a `downgrade base` / drop so each session starts from current migrations.
13. **Tests** — `tests/test_models.py` (relationships, constraints, snapshot behaviour) and `tests/test_seed.py` (exact counts, idempotency, no password rotation, deliberate duplicates).

**Out of scope (deferred):** any API endpoint or Pydantic schema (plans 03+); `AddOn` seed data (admin adds them later); the login/JWT side of `security.py` (plan 05); `services/clock.py` (plan 04); migrating a pre-existing database (this is greenfield — `downgrade base` may drop everything).

## Behaviour

Moves the build from state `scaffolded` to `schema-ready`. No runtime end-user flow; the "user" is a developer on `feature/database-models`.

1. Add `app/models/enums.py`, the ten model modules, and `app/models/__init__.py`.
2. `alembic revision --autogenerate -m "core catalog"`; hand-edit the generated `0001_core_catalog` (enum `create_type`, `server_default`s, check constraints, `ondelete`, `id=1` CK). Repeat → `0002_cart_orders_contact`.
3. `alembic upgrade head` against `eatddelight` → all 14 tables + 4 enums created. `alembic downgrade base` → clean teardown (enums dropped). Iterate until both directions are clean.
4. Add `app/core/security.py` (`hash_password` / `verify_password`).
5. Add `scripts/seed_menu.py`. Run `python -m scripts.seed_menu` → catalog loaded. Run again → row counts unchanged, no error.
6. Fill the `conftest.py` factory fixtures; switch the test-schema fixture to `alembic upgrade head`.
7. `pytest tests/test_models.py tests/test_seed.py` green; `ruff check` / `ruff format --check` / `mypy app` clean; the full suite (incl. `test_health`) still green.
8. Edit `plans/backend/02-database-models.md` to match this spec's `OrderStatus` + custom-field decisions. Commit `backend/` (+ the plan edit), push to `master`.

The seed runs **only** when invoked manually (`python -m scripts.seed_menu`) — never on app startup, never inside a migration. Tests call `seed()` directly from fixtures where a populated catalog is needed.

## Constraints

- Inherits `backend/specs/00-overview.md`: async SQLAlchemy 2.x + asyncpg, local PostgreSQL 18, `venv` + `pip`, `Decimal` money, timezone-aware timestamps, **every schema change via a hand-reviewed migration**, per-plan green gate (`ruff` + `mypy app` + `pytest`).
- **No new paid tooling.** Alembic and `passlib[bcrypt]` are already project dependencies. Switching the test-schema build to `alembic upgrade head` has **no cost** — it just runs the existing migrations once per test session (a second or two for 14 tables); nothing to install or subscribe to.
- `Numeric(8, 2)` caps values at 999,999.99 — ample for PKR menu prices (largest seeded is 900).
- Dish names are seeded **verbatim from the flyers**, typos included (`Khauasay`, `Ceasar`, `Sizler`, `Alo`, `Raps`). Correcting vs keeping is a client decision tracked in `backend/specs/00-overview.md` §hardening; `slug` values stay stable regardless.
- The `OrderStatus` value list and the four structured custom-order fields are **resolved decisions** from the `/spec 00` interview; `plans/backend/02-database-models.md` still shows the old 6-value enum and no structured fields and must be edited to agree.
- Enum value changes after this plan need a **manual** migration (autogenerate does not detect them) — the four enums must be right now.
- `.env`'s `OWNER_PASSWORD` is currently the placeholder `change-me-before-plan-02`; it must be set to a real value before `seed_menu.py` is run outside tests.
- Greenfield: no production data to preserve; `downgrade base` dropping everything is acceptable.

## Edge Cases and Error Handling

| Trigger | Expected Response |
|---|---|
| `seed_menu.py` run a 2nd / Nth time | Idempotent — no duplicate rows; category count stays 11, food count 42; mutable fields (price, description, flags) reset to seed values; only `updated_at` may move. |
| A seeded food's price was hand-edited, then seed re-run | Price is overwritten back to the seed value — documented as intended (upsert refreshes mutable fields), not a bug. |
| An `owner` `AdminUser` already exists when seed runs | No second owner is created; the existing `hashed_password` is left untouched. |
| `about_text` / `address` / `opening_hours` already set, seed re-run | Those three columns are left as-is (filled only when NULL); other `SiteSettings` fields refresh to seed values. |
| Delete a `Category` that has `Food` rows | `IntegrityError` — FK `ON DELETE RESTRICT`. (Surfaced as `category_in_use` by plan 05.) |
| Delete a `Food` referenced by `OrderItem` rows | Succeeds — `order_items.food_id` set to NULL; `food_name` snapshot retained so invoices/history still render. |
| Delete an `AddOn` referenced by `order_item_addons` | Succeeds — `addon_id` NULLed; `addon_name` + `unit_price` snapshots retained. |
| Delete a `Food` referenced by `CartItem` / `Favourite` | CASCADE — those rows are removed (carts are transient; a stale favourite simply disappears). |
| Insert a 2nd `SiteSettings` row (`id ≠ 1`) | Rejected by `ck_site_settings_singleton`; `id = 1` again rejected by the PK. |
| Insert a `Favourite` whose `(session_token, food_id)` already exists | `IntegrityError` on `uq_favourites_session_food` (plan 03's endpoint pre-checks / treats add as idempotent). |
| Insert a `Food` with `price <= 0` or `min_order_quantity < 1` | Rejected by the relevant check constraint. |
| Two "Alfredo Pasta" / two "Special Khauasay" dishes | Both persist as **separate** `Food` rows in different categories — the seed natural key is `(category_id, name, day_of_week)`, no dedupe. |
| `Order.total` / `subtotal` NULL for a `custom_request` awaiting a quote | Allowed — both columns nullable; plan 05's quote endpoint fills them. |
| `event_date` on a custom order is in the past | Not a DB constraint — a service rule in plan 04, same `advance_order_required` code as `requested_date`. |
| Autogenerated migration committed without hand-review | Process violation — must be diffed for missing enum creation, `server_default`, checks, `ondelete`, the singleton CK before commit. |
| `alembic upgrade head` run against a DB that already has some of these tables | Fails loudly ("relation already exists"); intended flow is empty DB → `upgrade head`, or `downgrade base` first to reset. |
| Test session starts against a stale `eatddelight_test` schema | `conftest.py` resets (`downgrade base` / drop) then `alembic upgrade head`, so every session matches current migrations. |
| `seed_menu.py` run before `alembic upgrade head` | Fails with "relation does not exist"; README/plan document the order (migrate, then seed). |

## Acceptance Criteria

- [ ] `alembic upgrade head` from an **empty** `eatddelight` creates all 14 tables, the 4 named enum types, and every unique / check / FK constraint under the `ix_/uq_/ck_/fk_/pk_` naming convention.
- [ ] `alembic downgrade base` removes every table **and** drops the 4 enum types with no error.
- [ ] Exactly two revision files exist — `*_0001_core_catalog.py` and `*_0002_cart_orders_contact.py` — each hand-edited (enum creation handled, `server_default`s, check constraints, `ondelete`, `id = 1` CK all present in the file).
- [ ] `python -m scripts.seed_menu` on a fresh migrated DB creates exactly: **11** categories, **42** foods (5 with `day_of_week` set, 37 with it NULL), **1** `SiteSettings` (id = 1), **1** `owner` `AdminUser`, **0** `AddOn`.
- [ ] Running `seed_menu` a second time changes no row counts and raises no error; a food whose price was hand-edited is reset to its seed value.
- [ ] Given an existing `owner` with password *X*, when `seed_menu` runs, then no second owner is created and `verify_password(X, owner.hashed_password)` is still `True`.
- [ ] "Alfredo Pasta with Sauce" (`day_of_week = thu`, price 600) and "Alfredo Pasta" (`house-favourites`, price 550) are distinct `Food` rows; likewise the two "Special Khauasay/Khousay".
- [ ] `hash_password("s3cret")` returns a bcrypt hash string; `verify_password("s3cret", <hash>)` is `True` and `verify_password("wrong", <hash>)` is `False`.
- [ ] `set(OrderStatus)` is exactly `{"pending", "confirmed", "completed", "cancelled"}`.
- [ ] `Order` has nullable columns `servings` (int), `budget_range` (str), `occasion` (str), `event_date` (date), `subtotal`, `total`, `custom_description`, `lookup_token`, `whatsapp_link_sent_at`.
- [ ] Deleting a `Category` with foods raises `IntegrityError`; deleting a `Food` referenced by an `OrderItem` succeeds, leaving `order_items.food_id` NULL and `food_name` intact.
- [ ] Inserting a duplicate `(session_token, food_id)` `Favourite` raises `IntegrityError`; inserting `SiteSettings` with `id = 2` raises `IntegrityError`.
- [ ] `Decimal("380.00")` round-trips through the DB as a 2-place `Decimal`; an `OrderItem.unit_price` set at insert time is unchanged after the referenced `Food.price` is later updated.
- [ ] `conftest.py` builds the test schema via `alembic upgrade head`; `pytest tests/test_models.py tests/test_seed.py` and the full suite are green; `ruff check` / `ruff format --check` / `mypy app` are clean.
- [ ] `plans/backend/02-database-models.md` is updated so its `OrderStatus` (4 values) and `Order` structured custom fields match this spec.

**Traceability:** every FR maps to ≥1 criterion — FR1→`set(OrderStatus)` + upgrade criteria; FR2/FR3→upgrade + relationship criteria; FR4→nullable-columns + delete/snapshot criteria; FR5→nullable-columns criterion; FR6→`OrderStatus` criterion; FR7→constraint criteria (RESTRICT, CASCADE/SET NULL, dup favourite, singleton, checks); FR8→`Decimal` round-trip criterion; FR9→upgrade/downgrade/revision-count criteria; FR10→hash/verify criterion; FR11→seed count + idempotency + owner + duplicates criteria; FR12→conftest criterion; FR13→green criterion; plus the plan-file-sync criterion. Every edge case is covered by a criterion or is explicitly a service/process concern handled in another plan.
