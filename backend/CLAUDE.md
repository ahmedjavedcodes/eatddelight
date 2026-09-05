# CLAUDE.md — Daughter's Delight Backend

**Daughter's Delight** is a home-kitchen food business API. 

## Business Context

- Home kitchen (Instagram: `@eatddelight`, phone: `0312-2252915`)
- Two menus: **Menu of the Day** (1 item/weekday, min qty 1) and **Full Menu** (à la carte, min qty 3)
- No customer accounts, no payment. Checkout → WhatsApp handoff or invoice download
- Admin roles: `owner` (full control + delete + staff mgmt) and `staff` (create/update only)

## Tech Stack

- **Framework:** FastAPI (async)
- **DB:** PostgreSQL + SQLAlchemy 2.x (async, asyncpg) + Alembic migrations
- **Validation:** Pydantic v2 (mirrors frontend constraints)
- **Auth:** JWT (access + refresh), bcrypt/argon2 password hashing
- **PDF invoices:** WeasyPrint (HTML → PDF)
- **Package mgmt:** `uv` + `python-dotenv`
- **Testing:** pytest + pytest-asyncio + httpx AsyncClient (disposable test DB per session)
- **Lint:** ruff (check + format) + mypy

## Core Domain Model

```
Category 1─* Food *─* AddOn (via food_addons; AddOn.is_global applies to all)
Order 1─* OrderItem *─* AddOn (via order_item_addons; prices snapshotted)
AdminUser (role: owner | staff)
SiteSettings (singleton)
ContactMessage (inbox)
```

**Food fields:** `id, category_id, name, description, price, image_url, is_available, min_order_quantity, is_single_serving, requires_advance_order, day_of_week` (nullable, for Menu of the Day only), timestamps

**Order:** `id, invoice_number, lookup_token, customer_{name,phone}, order_source (catalog|custom_request), requested_date, status (pending→confirmed→completed, cancelled from any non-terminal), subtotal, total, is_custom, custom_description, {servings, budget_range, occasion, event_date}` (nullable, for custom orders), created_at

**Key rule:** items can appear twice (e.g., "Alfredo" as Thursday special AND in House Favourites) — model as **separate Food rows**

## Business Rules (Pydantic + service layer)

1. **Advance order:** `requested_date ≥ tomorrow` (Asia/Karachi time)
2. **Day-of-week specials:** if `day_of_week` set, order date must match that day
3. **Min qty:** reject lines where `quantity < food.min_order_quantity`
4. **Availability:** reject unavailable foods/add-ons at order time (can change after add-to-cart)
5. **Price snapshot:** `OrderItem.unit_price` copied at order creation, never recomputed
6. **Role-based:** staff get 403 on DELETE; only owner can delete/manage staff/edit settings
7. **Custom orders:** may have `order_source='custom_request'` with zero catalog items + `total=0` until owner quotes

## API (`/api/v1/...`)

**Public (no auth):**
- `GET /settings` — business info (phone, WhatsApp, Instagram, about, hours)
- `POST /contact` — contact form submission
- `GET /menu` — full à la carte grouped by category
- `GET /weekly-menu` — 5 daily specials by weekday
- `GET /foods?search=&category_id=&day_of_week=&available=true` — filtered listing + pagination
- `GET /foods/{id}` — detail with resolved add-ons

**Admin (JWT required):**
- `POST /admin/auth/{login,refresh}`
- `POST/PUT /admin/{categories,foods,addons}`, `DELETE` (owner only)
- `GET /admin/orders`, `PATCH /admin/orders/{id}/status` (forward-only transitions)
- `GET/POST /admin/staff` (owner only)
- `PUT /admin/settings` (owner only)
- `GET /admin/contact-messages`, `PATCH .../{id}` (mark read)

**Not yet scoped:**
- `POST /orders` — create from cart + custom request
- `GET /orders/{id}` — lookup by id + short token (non-enumerable)
- `GET /orders/{id}/invoice` — PDF download

## Project Structure

```
app/
  api/v1/{endpoints, admin, deps.py}
  core/{config.py, security.py}
  db/{base.py, session.py}
  models/
  schemas/
  services/
  templates/
  main.py
alembic/versions/
scripts/seed_menu.py
tests/{conftest.py, test_*.py}
pyproject.toml
.env.example
```

## Testing & Migrations

- **Migrations:** Alembic per model change, hand-reviewed (autogenerate misses enum changes, renames)
- **Tests:** pytest + AsyncClient vs real test DB (per-session creation, per-test rollback). Cover: business rules (esp. Monday-ordered-Monday edge case), role checks (staff 403), uniqueness (invoice number, lookup token), WhatsApp message formatting
- **Lint:** `ruff check && ruff format --check` + mypy strict on `app/`; pre-commit hook

## Build Status

✅ Scaffolding, core models + migrations, seed script
✅ Public read APIs (menu, weekly-menu, categories, foods, settings)
✅ Admin auth + RBAC, admin CRUD (categories, foods, add-ons, staff, settings, orders, contact)
✅ Contact form (public POST, admin inbox)
⏳ Order creation (`POST /orders`), invoice PDF, checkout hardening
