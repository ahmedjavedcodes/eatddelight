# CLAUDE.md — Daughter's Delight (eatddelight) Backend

This file gives Claude Code full context to build the backend for **Daughter's Delight** (Instagram: `@eatddelight`), a home-kitchen food business. Read this file in full before writing code, and follow the phased build plan in Section 13 in order — each phase should be a working, tested increment, not a big-bang implementation.

## 1. Business Context

Daughter's Delight is a home kitchen run by the client's mother. They currently take orders through Instagram DMs (`@eatddelight`) and phone (`0312-2252915`). They sell two kinds of food:

1. **Menu of the Day** — a fixed weekly rotation. Each weekday has exactly one dish, available only on that day, single-serving, ordered at least one day in advance.
2. **Full Menu (à la carte)** — a larger catalog organized into categories (Rice, Gravy, etc.), minimum order quantity of 3 per item, subject to availability, also ordered at least one day in advance.

There is no online payment and no customer login. A customer browses the site, builds a cart (and/or submits a custom/bespoke order request), sees a plain order summary with prices at checkout, and then either downloads an invoice to send manually via WhatsApp, or clicks a button that opens WhatsApp with the order pre-filled as a message to the owner's number. The owner (and staff the owner adds) manage the menu through an admin panel.

**Decisions confirmed with the client (do not deviate without checking in):**
- No customer accounts. Cart/favourites are tied to an anonymous session/device token, not a user.
- No online payment gateway. Checkout only displays cart items and total price.
- Admin panel exists with two roles: `owner` and `staff`. Staff (added by the owner) can create/update categories, foods, and add-ons. **Only the owner can delete food items** (extended to categories/add-ons for consistency — flag this assumption to the client if it matters).
- Checkout redirects to the owner's WhatsApp chat with the order pre-filled; there's also an invoice download option.

## 2. Tech Stack

- **Framework:** FastAPI (async)
- **ORM:** SQLAlchemy 2.x (async engine, `asyncpg` driver)
- **DB:** PostgreSQL
- **Validation/schemas:** Pydantic v2 (`pydantic-settings` for config)
- **Migrations:** Alembic
- **Testing:** pytest, pytest-asyncio, httpx `AsyncClient` (ASGI transport) against a disposable test Postgres schema/database
- **Lint/format:** ruff (lint + format), mypy for type checking
- **Auth (admin only):** JWT access tokens, passwords hashed with `passlib[bcrypt]` or `argon2`
- **PDF invoices:** WeasyPrint (HTML→PDF) — simplest to theme; reportlab is an acceptable fallback if WeasyPrint's system deps are unavailable in the environment
- **Package/env management:** `uv` or `poetry` (pick one and be consistent); `python-dotenv`/`pydantic-settings` for env vars
- **Containerization:** docker-compose for local Postgres (+ the app itself, optionally)

## 3. Scope & Non-Goals

In scope: menu/catalog APIs, cart, favourites, order + invoice + WhatsApp handoff, custom order requests, admin CRUD, role-based permissions, contact form capture, site settings.

Explicitly **out of scope** unless the client asks later: customer accounts/login, online payments, SMS/email notifications, real-time order tracking, delivery logistics/routing, multi-tenant support (this is a single-business backend).

## 4. Domain Model & Relationships

Core relationship required by the client: **one Category has many Foods**. Add-ons attach to foods (many-to-many, with a "global" shortcut so an add-on can apply to every food without an explicit join row per food).

```
Category 1───* Food *───* AddOn   (via food_addons association table)
Food *───1 Category
Order 1───* OrderItem *───* AddOn (via order_item_addons, price snapshotted)
Order (custom_description, is_custom) for bespoke requests not tied to catalog items
Cart 1───* CartItem *───* AddOn   (via cart_item_addons)
Favourite (session_token, food_id) unique pair — no separate table needed beyond this
AdminUser (role: owner | staff)
SiteSettings — singleton row for about/contact/social content
ContactMessage — inbound contact form submissions
```

### Category
- `id`, `name`, `slug` (unique), `description` (nullable), `display_order` (int), `is_active`, timestamps

### Food
- `id`, `category_id` (FK → Category, `ON DELETE RESTRICT` unless admin explicitly cascades), `name`, `description`, `price` (Numeric(8,2)), `image_url`, `is_available` (bool), `min_order_quantity` (int, default 1 — set to 3 for full-menu items, 1 for daily specials per the flyers), `is_single_serving` (bool), `requires_advance_order` (bool, default `True` — both menus require 1-day advance), `day_of_week` (nullable enum `mon..fri` — set only for Menu-of-the-Day items; null for full-menu items), timestamps
- Note: the same dish name can legitimately appear twice (e.g. "Alfredo Pasta" is both Thursday's daily special at 600 and a House Favourites item at 550, and "Special Khousay"/"Khauasay" appears as both Wednesday's special and a Khousay-category item) — model these as **separate `Food` rows**, don't try to dedupe them.

### AddOn
- `id`, `name`, `price` (Numeric(8,2)), `is_available`, `is_global` (bool — if true, applies to every food automatically without a `food_addons` row), timestamps

### food_addons (association table)
- `food_id`, `addon_id` — only needed for non-global add-ons scoped to specific foods

### Cart / CartItem / cart_item_addons
- `Cart`: `id`, `session_token` (string/UUID, indexed, unique), `created_at`, `updated_at`
- `CartItem`: `id`, `cart_id`, `food_id`, `quantity`, `notes` (nullable, free text for e.g. spice level)
- `cart_item_addons`: `cart_item_id`, `addon_id`, `quantity`

### Favourite
- `id`, `session_token`, `food_id`, `created_at` — unique constraint on `(session_token, food_id)`

### Order / OrderItem / order_item_addons
- `Order`: `id`, `invoice_number` (unique, e.g. `DD-20260904-0001`), `customer_name`, `customer_phone`, `order_source` (enum: `catalog` | `custom_request`), `requested_date` (date — when the food should be ready, must be ≥ tomorrow in Asia/Karachi time), `status` (enum: `pending` → `confirmed` → `preparing` → `ready` → `delivered`, plus `cancelled`), `subtotal`, `total`, `is_custom` (bool), `custom_description` (nullable text — used when `order_source = custom_request`), `admin_notes` (nullable), `whatsapp_link_sent_at` (nullable timestamp), `created_at`
- `OrderItem`: `id`, `order_id`, `food_id` (nullable — null for a pure custom request line), `quantity`, `unit_price` (snapshot, not a live FK lookup), `notes`
- `order_item_addons`: `order_item_id`, `addon_id`, `quantity`, `unit_price` (snapshot)

### AdminUser
- `id`, `name`, `email` (unique), `hashed_password`, `role` (enum: `owner` | `staff`), `is_active`, `created_at`
- Seed exactly one `owner` account on first migration/seed run from env vars (`OWNER_EMAIL`, `OWNER_PASSWORD`) — never hardcode credentials in source.

### SiteSettings (singleton — enforce with a check constraint or just always use id=1)
- `business_name`, `tagline`, `about_text`, `contact_phone`, `whatsapp_number` (E.164, e.g. `923122252915` — this is what the wa.me link uses, distinct from the display-formatted `0312-2252915`), `instagram_handle`, `address` (nullable), `opening_hours` (nullable), `updated_at`

### ContactMessage
- `id`, `name`, `phone_or_email`, `message`, `created_at`, `is_read` (bool, for admin inbox)

## 5. Extracted Menu Data (seed reference)

Extracted from the two flyer images provided. Use this as the source for a `scripts/seed_menu.py` (or Alembic data migration) in Phase 1. Prices are in PKR.

**Menu of the Day** (category "Menu of the Day", one Food per weekday, `is_single_serving=True`, `min_order_quantity=1`):

| Day | Item | Price |
|---|---|---|
| Monday | Makhni Handi with Salad+Roti | 600 |
| Tuesday | Chicken Spicy Mandi with Sauces | 600 |
| Wednesday | Special Khauasay with Curry | 550 |
| Thursday | Alfredo Pasta with Sauce | 600 |
| Friday | Chicken Biryani with Raita + Salad | 500 |

**Full Menu** (category → items → price, `min_order_quantity=3` unless noted):

- **Rice**: Chicken Biryani 400, Spicy Mandi 600, Peas Pulao 300, Fried Rice 400, Beef Biryani 480
- **Gravy**: Boneless Makhni Handi 600, Chicken Haleem 380, Chicken Achari 350, Seekh Kabab Handi 550, Chicken Kofta 350, Desi Dam Qeema 450, Chicken Nihari 480
- **Meat-y**: Alo Goshat 380, Seekh Kabab 300, Beef Handi 600
- **Dal with Tarka**: Dal Chana with Tarka 250, Makhni Dal 300, Dal Chawal 300, Dal Mong Special 250, Dal Mash with Spice 300
- **Chinese**: Shashlik with Rice 650, Jalfrezi with Rice 650
- **Khousay**: Special Khousay 550, Curry Pakora 250
- **Fit and Healthy**: Russian Salad 350, Ceasar Salad 480, Asian Salad 350, Hummus with Bread 600
- **Desi Vegetarian**: Sizler Bhindi 280, Mix Sabzi 250, Alo Palak 250
- **House Favourites**: Alfredo Pasta 550, Chicken Raps 380
- **Sweet Snack**: Brownies 280, Special Kheer 300, Zarda 250, Kunafa 900

Global flyer notes to encode as validation/business rules (Section 7): all items single-serving; orders placed at least one day in advance; full-menu items have a minimum order quantity of 3; items subject to availability (`is_available` flag).

Contact/brand data for `SiteSettings` seed: `business_name="Daughter's Delight"`, `tagline="Homemade Made with Love"`, `contact_phone="0312-2252915"`, `whatsapp_number="923122252915"`, `instagram_handle="eatddelight"`.

## 6. API Design

The client listed frontend pages (`/home`, `/about`, `/contact`, `/weekly-menu`, `/menu`, cart, favourites, checkout). These are frontend routes, not backend endpoints — the backend exposes a versioned REST API (`/api/v1/...`) that those pages consume. Mapping:

**Public (no auth):**
- `GET /api/v1/settings` — business info for Home/About/Contact/footer (phone, WhatsApp, Instagram, about text, hours)
- `POST /api/v1/contact` — submit a contact message
- `GET /api/v1/categories` — list categories (excludes "Menu of the Day" from the full-menu listing, or filter client-side by a `kind` query param — see note below)
- `GET /api/v1/categories/{id}/foods` — foods in a category
- `GET /api/v1/menu` — full à la carte menu grouped by category, for `/menu`
- `GET /api/v1/weekly-menu` — the 5 daily specials grouped by weekday, for `/weekly-menu`
- `GET /api/v1/foods/{id}` — food detail including its resolved add-ons (global + food-specific)
- `GET /api/v1/foods?search=&category_id=&day_of_week=&available=true` — filtered listing, used for search/menu filtering
- `GET|POST /api/v1/cart` — get-or-create a cart for a session token (see Section 8 for session-token handling)
- `POST/PATCH/DELETE /api/v1/cart/items/{item_id}` — add/update/remove a cart line
- `GET/POST/DELETE /api/v1/favourites` — list/add/remove favourites for a session token
- `POST /api/v1/orders` — create an order (from the current cart, and/or with a `custom_description` for a bespoke request); returns the order, its invoice number, and a ready-to-use `whatsapp_url`
- `GET /api/v1/orders/{id}` — order confirmation lookup (by id + a short token, not enumerable — don't let random order IDs leak other customers' data)
- `GET /api/v1/orders/{id}/invoice` — download the invoice as PDF

**Admin (JWT required):**
- `POST /api/v1/admin/auth/login`, `POST /api/v1/admin/auth/refresh`
- `POST/PUT /api/v1/admin/categories`, `DELETE /api/v1/admin/categories/{id}` (owner only)
- `POST/PUT /api/v1/admin/foods`, `DELETE /api/v1/admin/foods/{id}` (owner only)
- `POST/PUT /api/v1/admin/addons`, `DELETE /api/v1/admin/addons/{id}` (owner only)
- `GET /api/v1/admin/orders`, `PATCH /api/v1/admin/orders/{id}/status`
- `GET/POST /api/v1/admin/staff`, `PATCH /api/v1/admin/staff/{id}` (owner only — manage staff accounts)
- `PUT /api/v1/admin/settings` (owner only, or owner+staff — confirm with client if staff should be allowed to edit About/Contact copy)
- `GET /api/v1/admin/contact-messages`, `PATCH .../{id}` (mark read)

Note on `/menu` vs `/weekly-menu`: rather than a `kind` flag on `Category`, keep "Menu of the Day" as an ordinary `Category` (satisfies the required one-to-many relationship cleanly) and give `/api/v1/weekly-menu` its own query (`WHERE category.slug = 'menu-of-the-day'` or `WHERE food.day_of_week IS NOT NULL`) so the two endpoints stay semantically distinct for the frontend even though they share the same underlying tables.

## 7. Business Rules & Validation

Enforce these in Pydantic validators / service-layer functions, not just at the DB level (DB constraints as a backstop, not the primary defense):

1. **Advance ordering:** `Order.requested_date` must be at least 1 day after "now" in Asia/Karachi time (the business's timezone), for both catalog and custom orders.
2. **Day-of-week specials:** if a `Food` has `day_of_week` set, any order line referencing it must have `Order.requested_date.weekday()` match that day. Combined with rule 1: if today is Monday, the earliest valid date for Monday's special is next Monday, not tomorrow.
3. **Minimum order quantity:** reject (or clamp with a clear error) any cart/order line where `quantity < food.min_order_quantity`.
4. **Availability:** reject lines for foods/add-ons where `is_available = False` at order time, even if they were in the cart earlier.
5. **Price snapshotting:** `OrderItem.unit_price` and `order_item_addons.unit_price` are copied from the current `Food`/`AddOn` price at order creation time and never recomputed later, so historical orders stay accurate if prices change.
6. **Role-based deletes:** `staff` accounts get 403 on any `DELETE` admin endpoint; only `owner` can delete. Staff can still create/update.
7. **Custom orders:** `order_source = 'custom_request'` orders may have zero catalog `OrderItem`s and rely on `custom_description`; `total` is nullable/`0` until the owner reviews and sets a price via the admin order endpoint (add an admin-only `PATCH /orders/{id}/quote` or fold it into the status-update endpoint).

## 8. WhatsApp Checkout & Invoice Flow

No accounts means "session" is just an opaque token, not a login:

- Frontend generates a UUID on first visit, stores it (cookie or localStorage — frontend's call), and sends it as a header (e.g. `X-Session-Token`) on cart/favourites/order requests. The backend never needs to issue or validate this token beyond using it as a lookup key — don't build session expiry/auth logic around it, it's just a bucket ID.
- On `POST /api/v1/orders`, after creating the order, build:
  - `whatsapp_url = f"https://wa.me/{settings.whatsapp_number}?text={urllib.parse.quote(message)}"` where `message` is a formatted plain-text summary (invoice number, each item × qty with add-ons, requested date, total, customer name/phone).
  - An invoice download link: `/api/v1/orders/{id}/invoice`.
- The frontend then offers both buttons: "Order on WhatsApp" (navigates to `whatsapp_url`) and "Download Invoice" (fetches the PDF for the customer to attach manually in WhatsApp). The backend just needs to produce both artifacts correctly — it doesn't send anything itself.
- Invoice PDF: simple themed one-pager (business name/logo, invoice number, date, customer name/phone, line items with add-ons, subtotal/total, "Homemade Made with Love" footer). Render an HTML template with Jinja2 and convert via WeasyPrint.

## 9. Custom Orders

A custom order is any request that doesn't map cleanly to catalog items (e.g., a bespoke cake or bulk catering order). Model this as an `Order` with `order_source='custom_request'` and a `custom_description` field; it can optionally still include real `OrderItem`s alongside the free-text description (e.g., "5x Chicken Biryani + a custom cake, details below"). Since there's no payment/account system, the flow is: customer submits the request → it lands in the admin order queue as `status='pending'` with no confirmed total → owner reviews it (likely coordinates final pricing over WhatsApp/phone, outside the system) → owner updates `status` and, if needed, sets `total` via the admin endpoint. Don't try to build an automated quoting engine — this is intentionally a manual step for the owner.

## 10. Auth & Permissions

- Admin auth only; customers are never authenticated.
- JWT bearer tokens for `AdminUser`. Keep it simple: login issues a short-lived access token (and optionally a refresh token) — no need for OAuth providers, magic links, etc.
- Two roles: `owner`, `staff`. Implement as a FastAPI dependency, e.g. `require_role("owner")`, layered on top of a base `get_current_admin_user` dependency. Every admin router should declare the roles it accepts explicitly rather than relying on implicit defaults.
- Only the `owner` role can: delete categories/foods/add-ons, manage staff accounts (create/deactivate), and (pending client confirmation) edit `SiteSettings`.

## 11. Project Structure

```
app/
  api/
    v1/
      endpoints/        # public: menu, cart, favourites, orders, contact, settings
      admin/            # admin: auth, categories, foods, addons, orders, staff, settings
      deps.py           # shared dependencies (db session, current admin user, role checks)
  core/
    config.py           # pydantic-settings
    security.py          # password hashing, JWT
  db/
    base.py              # SQLAlchemy declarative base, session factory
    session.py
  models/                # SQLAlchemy models, one module per aggregate
  schemas/               # Pydantic request/response models
  services/              # business logic (order creation, invoice generation, whatsapp link builder)
  templates/             # Jinja2 invoice HTML template
  main.py
alembic/
  versions/
scripts/
  seed_menu.py           # loads Section 5's data
tests/
  conftest.py            # test DB fixture, async client fixture, factory fixtures
  test_menu.py
  test_cart.py
  test_orders.py
  test_admin_auth.py
  test_admin_permissions.py
docker-compose.yml
pyproject.toml
alembic.ini
.env.example
```

## 12. Testing, Linting, Migrations

- **Migrations:** every model change ships with an Alembic revision generated via `alembic revision --autogenerate`, reviewed by hand before committing (autogenerate misses some things — enum changes, renames). Never edit the DB schema without a migration.
- **Tests:** pytest + pytest-asyncio, httpx `AsyncClient` against the FastAPI app with `ASGITransport`, a real (disposable) Postgres test database created/migrated per test session, and per-test transaction rollback for isolation. Cover: model relationships, each business rule in Section 7 (advance-order date math is the easiest thing to get subtly wrong — test the Monday-ordered-on-Monday edge case explicitly), role-based permission checks (staff 403 on delete), order/invoice number uniqueness, and the WhatsApp link/message formatting.
- **Lint/format:** ruff for both lint and format; run `ruff check` and `ruff format --check` in CI/pre-commit. Add mypy with reasonably strict settings on `app/` (loosen for `tests/` if needed).
- **Pre-commit:** hook up ruff + mypy + pytest (at least on changed files) so issues are caught before commit.

## 13. Build Plan (execute in this order)

1. **Scaffolding:** pyproject + dependency setup, FastAPI app skeleton, `pydantic-settings` config, docker-compose Postgres, Alembic init, ruff/mypy/pre-commit config, empty pytest setup with a working DB fixture (a trivial `test_health.py` hitting a `/health` endpoint should pass before moving on).
2. **Core models + migrations:** `Category`, `Food`, `AddOn`, `food_addons`. Write `scripts/seed_menu.py` using Section 5's data. Tests: relationships load correctly, seed script is idempotent (safe to re-run).
3. **Public read APIs:** `/menu`, `/weekly-menu`, `/categories`, `/foods` (with filters), `/settings`. Tests for each, including the Menu-of-the-Day vs full-menu distinction.
4. **Cart & Favourites:** models, session-token-scoped endpoints, quantity/min-order/availability validation on add-to-cart. Tests including the min-quantity and availability edge cases.
5. **Orders & Checkout:** `Order`/`OrderItem`/`order_item_addons` models, `POST /orders` (from cart and/or custom request), advance-order + day-of-week validation (Section 7, rules 1–2), invoice numbering, WhatsApp URL builder. Tests covering every validation rule and the message/URL format.
6. **Invoice PDF:** Jinja2 template + WeasyPrint rendering, `GET /orders/{id}/invoice`. Test that it returns a valid PDF with correct line items/total.
7. **Admin auth & RBAC:** `AdminUser` model + seed owner account, JWT login, `require_role` dependency. Tests for login, token validation, and role enforcement.
8. **Admin CRUD:** categories/foods/add-ons (create/update for staff+owner, delete owner-only), staff management (owner-only), order management (list/update status, set quote total for custom orders), settings update. Tests per permission boundary.
9. **Contact form:** `ContactMessage` model, public POST, admin list/mark-read.
10. **Hardening:** CORS config for the actual frontend origin(s), request rate limiting on public write endpoints (cart/orders/contact — cheap abuse vector with no auth), structured logging, consistent error response shape, OpenAPI docs cleanup (tags, examples, response models everywhere).
11. **Final pass:** full test suite green, ruff/mypy clean, review the seed data against the flyer images once more for typos (the flyers themselves have some, e.g. "Khauasay" vs "Khousay", "Ceasar" vs "Caesar", "Alo Goshat"/"Alo Palak" vs "Aloo" — decide with the client whether to correct these in the displayed name or keep them verbatim).

## 14. Open Questions for the Client (flag, don't guess silently)

- Should `staff` be allowed to edit `SiteSettings` (About/Contact copy), or is that owner-only too?
- For custom order requests, is any structured input needed (servings count, budget range, occasion) beyond a free-text description?
- Order `status` values above are a reasonable default (`pending → confirmed → preparing → ready → delivered`, plus `cancelled`) — confirm this matches how the kitchen actually tracks an order.
