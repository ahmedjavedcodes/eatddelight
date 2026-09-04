# 02 — Database Models, Migrations & Seed

**Purpose:** Define every SQLAlchemy model (all tables from CLAUDE.md §4), the enum types, constraints, the Alembic migration strategy, and an idempotent seed script loading the §5 menu data plus `SiteSettings` and the single owner account.

**Implements from `backend/CLAUDE.md`:** §4 (domain model — all entities), §5 (seed data), §7 rule 5 (price snapshot columns exist), §13 phase 2.

**Prerequisites:** [01-fastapi-scaffolding.md](01-fastapi-scaffolding.md).

**Definition of done:**
- `uv run alembic upgrade head` from empty builds every table + enum.
- `uv run python -m scripts.seed_menu` run **twice** leaves the DB identical (row counts unchanged, no duplicates, no errors).
- `uv run pytest tests/test_models.py tests/test_seed.py` green.
- `ruff` / `mypy` clean.

---

## 1. Module layout (`app/models/`)

| Module | Contents |
|---|---|
| `enums.py` | `DayOfWeek`, `OrderSource`, `OrderStatus`, `AdminRole` |
| `category.py` | `Category` |
| `food.py` | `Food`, `food_addons` table |
| `addon.py` | `AddOn` |
| `cart.py` | `Cart`, `CartItem`, `cart_item_addons` table |
| `favourite.py` | `Favourite` |
| `order.py` | `Order`, `OrderItem`, `order_item_addons` table |
| `admin_user.py` | `AdminUser` |
| `site_settings.py` | `SiteSettings` |
| `contact_message.py` | `ContactMessage` |
| `__init__.py` | imports every module so `Base.metadata` is complete (Alembic + tests rely on this) |

All models inherit `Base`; all except pure association tables use `TimestampMixin` (from [01 §3](01-fastapi-scaffolding.md#3-appdbbasepy)) unless a table's field list below says otherwise. All monetary columns `Numeric(8, 2)` mapped to `Decimal`.

## 2. Enums (`app/models/enums.py`)

```python
import enum

class DayOfWeek(enum.StrEnum):
    mon = "mon"; tue = "tue"; wed = "wed"; thu = "thu"; fri = "fri"

class OrderSource(enum.StrEnum):
    catalog = "catalog"; custom_request = "custom_request"

class OrderStatus(enum.StrEnum):
    pending = "pending"; confirmed = "confirmed"; completed = "completed"
    cancelled = "cancelled"

class AdminRole(enum.StrEnum):
    owner = "owner"; staff = "staff"
```

Mapped with `sa.Enum(DayOfWeek, name="day_of_week")` etc. — named types, created explicitly in the first migration. **Revised from the original 6-value draft** (`pending/confirmed/preparing/ready/delivered/cancelled`) via the `/spec 02` interview, resolving the §14 open question: the simplified 4-value set is `pending → confirmed → completed` (+ `cancelled` from any non-terminal state), forward-only transitions.

## 3. Entity field tables

### 3.1 `Category` (`categories`)

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `name` | `str(120)` | |
| `slug` | `str(140)` | **unique**, indexed; kebab-case, generated from name at write time |
| `description` | `str(500)` | nullable |
| `display_order` | `int` | default `0`; menu ordering |
| `is_active` | `bool` | default `True` |
| `created_at`, `updated_at` | tz `datetime` | from `TimestampMixin` |

Relationship: `foods: Mapped[list["Food"]]` — `back_populates="category"`, `passive_deletes=True` (DB enforces RESTRICT, see Food FK).

### 3.2 `Food` (`foods`)

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `category_id` | `int` FK → `categories.id` | `ondelete="RESTRICT"`, indexed, not null |
| `name` | `str(160)` | duplicates across categories allowed (see §5 note) |
| `description` | `str(1000)` | nullable |
| `price` | `Numeric(8,2)` → `Decimal` | not null, `> 0` (CK) |
| `image_url` | `str(500)` | nullable |
| `is_available` | `bool` | default `True` |
| `min_order_quantity` | `int` | default `1`; `3` for full-menu items, `1` for daily specials; CK `>= 1` |
| `is_single_serving` | `bool` | default `True` (all flyer items are) |
| `requires_advance_order` | `bool` | default `True` (both menus need ≥1 day) |
| `day_of_week` | `sa.Enum(DayOfWeek)` | **nullable** — set only for Menu-of-the-Day items |
| `created_at`, `updated_at` | tz `datetime` | |

Relationships:
- `category: Mapped["Category"]` — `back_populates="foods"`.
- `addons: Mapped[list["AddOn"]]` — `secondary="food_addons"`, `lazy="selectin"` (menu detail is read-heavy). This is only the *explicit* non-global links; global add-ons are unioned in the service layer (see [03 §Foods](03-public-catalog-cart-favourites.md)).

Index: `ix_foods_category_id`, partial-ish index on `day_of_week` (plain index is fine) for `/weekly-menu`.

### 3.3 `AddOn` (`addons`)

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `name` | `str(120)` | |
| `price` | `Numeric(8,2)` → `Decimal` | not null, `>= 0` (CK) |
| `is_available` | `bool` | default `True` |
| `is_global` | `bool` | default `False` — if `True`, applies to every food without a `food_addons` row |
| `created_at`, `updated_at` | tz `datetime` | |

### 3.4 `food_addons` (association table)

Plain `Table` (no model class):

| Column | Notes |
|---|---|
| `food_id` | FK → `foods.id`, `ondelete="CASCADE"` |
| `addon_id` | FK → `addons.id`, `ondelete="CASCADE"` |

PK = `(food_id, addon_id)`. Only rows for **non-global** add-ons scoped to specific foods.

### 3.5 `Cart` (`carts`)

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `session_token` | `str(64)` | **unique**, indexed — the `X-Session-Token` value |
| `created_at`, `updated_at` | tz `datetime` | |

Relationship: `items: Mapped[list["CartItem"]]` — `cascade="all, delete-orphan"`, `lazy="selectin"`.

### 3.6 `CartItem` (`cart_items`)

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `cart_id` | `int` FK → `carts.id` `ondelete="CASCADE"` | indexed |
| `food_id` | `int` FK → `foods.id` `ondelete="CASCADE"` | not null |
| `quantity` | `int` | CK `>= 1` (min-order-qty enforced in service, not CK) |
| `notes` | `str(300)` | nullable — e.g. spice level |
| `created_at`, `updated_at` | tz `datetime` | |

Relationships: `food`, `addon_links: Mapped[list["CartItemAddon"]]`.

> Decision: `cart_item_addons` **is** modelled as a class (`CartItemAddon`) because it carries `quantity`. Same for `order_item_addons`.

### 3.7 `CartItemAddon` (`cart_item_addons`)

| Column | Type | Notes |
|---|---|---|
| `cart_item_id` | `int` FK → `cart_items.id` `ondelete="CASCADE"` | PK part |
| `addon_id` | `int` FK → `addons.id` `ondelete="CASCADE"` | PK part |
| `quantity` | `int` | CK `>= 1` |

PK = `(cart_item_id, addon_id)`. No timestamps.

### 3.8 `Favourite` (`favourites`)

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `session_token` | `str(64)` | indexed |
| `food_id` | `int` FK → `foods.id` `ondelete="CASCADE"` | |
| `created_at` | tz `datetime` | (no `updated_at` — flag `TimestampMixin` not used; add `created_at` explicitly) |

Constraint: **unique `(session_token, food_id)`** → `uq_favourites_session_token` (naming convention will name it; add explicit `UniqueConstraint("session_token", "food_id", name="uq_favourites_session_food")`).

### 3.9 `Order` (`orders`)

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `invoice_number` | `str(24)` | **unique**, e.g. `DD-20260904-0001` |
| `lookup_token` | `str(32)` | indexed; random `secrets.token_urlsafe(16)`; required with `id` to fetch an order (non-enumerable) — **addition beyond §4**, see [00 §13](00-overview.md#13-assumptions-being-made-flag-if-any-matter-to-the-client) |
| `customer_name` | `str(120)` | not null |
| `customer_phone` | `str(32)` | not null |
| `order_source` | `sa.Enum(OrderSource)` | `catalog` \| `custom_request` |
| `requested_date` | `date` | when food should be ready; must be ≥ tomorrow Asia/Karachi (service rule) |
| `status` | `sa.Enum(OrderStatus)` | default `pending` |
| `subtotal` | `Numeric(8,2)` → `Decimal` | nullable for pure custom until quoted; else sum of line snapshots |
| `total` | `Numeric(8,2)` → `Decimal` | **nullable** — `NULL`/`0` for unpriced `custom_request` (§7 rule 7) |
| `is_custom` | `bool` | default `False`; convenience mirror of `order_source == custom_request` |
| `custom_description` | `Text` | nullable; used when `order_source = custom_request` |
| `admin_notes` | `Text` | nullable |
| `whatsapp_link_sent_at` | tz `datetime` | nullable — set when frontend reports the handoff (optional endpoint) |
| `servings` | `int` | nullable — **structured custom-order field**, added via the `/spec 02` interview |
| `budget_range` | `str(60)` | nullable — structured custom-order field |
| `occasion` | `str(120)` | nullable — structured custom-order field |
| `event_date` | `date` | nullable — structured custom-order field; when set, subject to the same ≥ tomorrow Asia/Karachi rule as `requested_date` |
| `created_at` | tz `datetime` | (no `updated_at` in §4; add it anyway via `TimestampMixin` for admin status tracking — note this as a minor addition) |

All four structured fields are optional; `custom_description` remains the only required field when `order_source = custom_request`.

Relationships: `items: Mapped[list["OrderItem"]]` (`cascade="all, delete-orphan"`, `lazy="selectin"`).

CK: `is_custom` true ⇔ `order_source = 'custom_request'` (optional, or trust the service).

### 3.10 `OrderItem` (`order_items`)

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `order_id` | `int` FK → `orders.id` `ondelete="CASCADE"` | indexed |
| `food_id` | `int` FK → `foods.id` `ondelete="SET NULL"` | **nullable** — null for a pure custom line; SET NULL so deleting a food never breaks history |
| `food_name` | `str(160)` | snapshot of the food name at order time (so invoices/history survive food deletion) — **addition**, keeps invoices renderable |
| `quantity` | `int` | CK `>= 1` |
| `unit_price` | `Numeric(8,2)` → `Decimal` | **snapshot**, never recomputed (§7 rule 5) |
| `notes` | `str(300)` | nullable |

Relationship: `addon_links: Mapped[list["OrderItemAddon"]]`.

### 3.11 `OrderItemAddon` (`order_item_addons`)

| Column | Type | Notes |
|---|---|---|
| `order_item_id` | `int` FK → `order_items.id` `ondelete="CASCADE"` | PK part |
| `addon_id` | `int` FK → `addons.id` `ondelete="SET NULL"` | PK part → cannot be null in a PK; use surrogate `id` PK instead and keep `addon_id` nullable |
| `addon_name` | `str(120)` | snapshot |
| `quantity` | `int` | CK `>= 1` |
| `unit_price` | `Numeric(8,2)` → `Decimal` | **snapshot** |

> Because `addon_id` needs `ON DELETE SET NULL` for history safety, give this table its own `id` PK and a `UniqueConstraint(order_item_id, addon_id)`.

### 3.12 `AdminUser` (`admin_users`)

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `name` | `str(120)` | |
| `email` | `str(255)` | **unique**, indexed, stored lowercased |
| `hashed_password` | `str(255)` | bcrypt/argon2 hash — never plaintext |
| `role` | `sa.Enum(AdminRole)` | `owner` \| `staff` |
| `is_active` | `bool` | default `True`; deactivate instead of delete |
| `created_at` | tz `datetime` | |

Seed exactly one `owner` on first seed run from `OWNER_EMAIL` / `OWNER_PASSWORD` (see §6). Never hardcode credentials.

### 3.13 `SiteSettings` (`site_settings`) — singleton

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | CK `id = 1` (enforce singleton); seed/upsert always id=1 |
| `business_name` | `str(120)` | |
| `tagline` | `str(200)` | nullable |
| `about_text` | `Text` | nullable |
| `contact_phone` | `str(32)` | display format, e.g. `0312-2252915` |
| `whatsapp_number` | `str(20)` | E.164 digits, e.g. `923122252915` — used for `wa.me` links |
| `instagram_handle` | `str(60)` | e.g. `eatddelight` |
| `address` | `str(300)` | nullable |
| `opening_hours` | `str(300)` | nullable |
| `updated_at` | tz `datetime` | |

### 3.14 `ContactMessage` (`contact_messages`)

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `name` | `str(120)` | |
| `phone_or_email` | `str(255)` | free text, one field |
| `message` | `Text` | not null |
| `is_read` | `bool` | default `False` — admin inbox |
| `created_at` | tz `datetime` | |

## 4. Constraint summary (put behind the service-layer checks)

| Constraint | Table |
|---|---|
| `uq_categories_slug` | categories |
| `uq_orders_invoice_number` | orders |
| `uq_favourites_session_food` (`session_token`, `food_id`) | favourites |
| `uq_carts_session_token` | carts |
| `ck_foods_price_positive` (`price > 0`) | foods |
| `ck_foods_min_qty` (`min_order_quantity >= 1`) | foods |
| `ck_addons_price_nonneg` (`price >= 0`) | addons |
| `ck_*_quantity_positive` | cart_items, cart_item_addons, order_items, order_item_addons |
| `ck_site_settings_singleton` (`id = 1`) | site_settings |
| FK `foods.category_id` → `RESTRICT` | foods |
| FK `order_items.food_id` / `order_item_addons.addon_id` → `SET NULL` | order history safety |
| FK cart/order child rows → `CASCADE` | |

## 5. Migration strategy

- **Two reviewed revisions up front** (later plans add endpoints, not schema):
  1. `0001_core_catalog` — enums, `categories`, `foods`, `addons`, `food_addons`, `site_settings`, `admin_users`.
  2. `0002_cart_orders_contact` — `carts`, `cart_items`, `cart_item_addons`, `favourites`, `orders`, `order_items`, `order_item_addons`, `contact_messages`.
- Generate with `alembic revision --autogenerate -m "..."`, then **hand-edit**: verify enum `create_type`, `server_default`s, check constraints, `ondelete` clauses, and the `id = 1` singleton CK — autogenerate misses all of these.
- Downgrade paths must drop enums (`sa.Enum(...).drop(op.get_bind())`).
- After this, switch `conftest.py` from `create_all` to `alembic upgrade head` so tests exercise the real migrations (optional but recommended before plan 03).

## 6. `scripts/seed_menu.py`

Idempotent. Safe to run any number of times. Structure:

```python
async def seed(session: AsyncSession) -> None:
    await seed_site_settings(session)     # upsert id=1
    await seed_owner(session)             # from env; only if no owner exists
    await seed_categories_and_foods(session)
    await session.commit()
```

- **Idempotency keys:** `Category` by `slug`; `Food` by `(category_id, name, day_of_week)` natural key (so the two "Alfredo Pasta" rows and the two "Special Khousay" rows stay distinct and are each matched correctly). Upsert = "get or create, then update mutable fields (price, description, flags)".
- **`SiteSettings`:** get row id=1 or create it; set `business_name="Daughter's Delight"`, `tagline="Homemade Made with Love"`, `contact_phone="0312-2252915"`, `whatsapp_number="923122252915"`, `instagram_handle="eatddelight"`. Do **not** overwrite `about_text`/`address`/`opening_hours` if already set by an admin (only fill when null).
- **Owner:** if `select(AdminUser).where(role == owner)` returns nothing, create one from `OWNER_EMAIL` / `OWNER_PASSWORD` / `OWNER_NAME` (hash via `app.core.security.hash_password` — that module lands in plan 05; until then, inline `passlib` here and refactor). If an owner exists, do nothing (never rotate the password from seed).

### 6.1 Menu of the Day (category `menu-of-the-day`, `display_order = 0`)

`is_single_serving=True`, `min_order_quantity=1`, `requires_advance_order=True`, `day_of_week` set.

| `day_of_week` | name | price |
|---|---|---|
| `mon` | Makhni Handi with Salad+Roti | 600 |
| `tue` | Chicken Spicy Mandi with Sauces | 600 |
| `wed` | Special Khauasay with Curry | 550 |
| `thu` | Alfredo Pasta with Sauce | 600 |
| `fri` | Chicken Biryani with Raita + Salad | 500 |

### 6.2 Full Menu (all `min_order_quantity=3`, `day_of_week=NULL`, `is_single_serving=True`)

`display_order` follows list order below (1..10).

| Category (slug) | Items — name: price (PKR) |
|---|---|
| Rice (`rice`) | Chicken Biryani: 400 · Spicy Mandi: 600 · Peas Pulao: 300 · Fried Rice: 400 · Beef Biryani: 480 |
| Gravy (`gravy`) | Boneless Makhni Handi: 600 · Chicken Haleem: 380 · Chicken Achari: 350 · Seekh Kabab Handi: 550 · Chicken Kofta: 350 · Desi Dam Qeema: 450 · Chicken Nihari: 480 |
| Meat-y (`meat-y`) | Alo Goshat: 380 · Seekh Kabab: 300 · Beef Handi: 600 |
| Dal with Tarka (`dal-with-tarka`) | Dal Chana with Tarka: 250 · Makhni Dal: 300 · Dal Chawal: 300 · Dal Mong Special: 250 · Dal Mash with Spice: 300 |
| Chinese (`chinese`) | Shashlik with Rice: 650 · Jalfrezi with Rice: 650 |
| Khousay (`khousay`) | Special Khousay: 550 · Curry Pakora: 250 |
| Fit and Healthy (`fit-and-healthy`) | Russian Salad: 350 · Ceasar Salad: 480 · Asian Salad: 350 · Hummus with Bread: 600 |
| Desi Vegetarian (`desi-vegetarian`) | Sizler Bhindi: 280 · Mix Sabzi: 250 · Alo Palak: 250 |
| House Favourites (`house-favourites`) | Alfredo Pasta: 550 · Chicken Raps: 380 |
| Sweet Snack (`sweet-snack`) | Brownies: 280 · Special Kheer: 300 · Zarda: 250 · Kunafa: 900 |

> Names are transcribed **verbatim from the flyers** (typos and all: "Khauasay", "Ceasar", "Alo", "Raps", "Sizler"). Correcting them is a client decision — see the hardening checklist in [00 §11](00-overview.md#11-phase-1011--hardening--release-checklist). If corrected later, keep `slug` stable.

- **Add-ons:** the flyers list none, so seed **no** `AddOn` rows. The model + resolution logic exist for the admin to add them later (e.g. a global "Extra Raita").

## 7. Tests

### `tests/test_models.py`
- Category ↔ Food one-to-many: create a category with 3 foods, reload, assert `category.foods` length and `food.category` backref.
- Add-on resolution inputs: create 1 global add-on + 1 food-specific link; assert the raw `food.addons` holds only the specific one (union with global is a service concern, tested in plan 03).
- `Favourite` unique pair: inserting the same `(session_token, food_id)` twice raises `IntegrityError`.
- FK RESTRICT: deleting a `Category` that has foods raises `IntegrityError`.
- `SiteSettings` singleton: inserting a row with `id != 1` raises (CK), second `id=1` insert raises (PK).
- Money round-trips as `Decimal` with 2 places.
- `OrderItem.unit_price` persists independently of later `Food.price` change (snapshot behaviour at the column level).

### `tests/test_seed.py`
- Run `seed()` on a fresh DB → assert exact counts: 11 categories, 5 daily + 37 full-menu = 42 foods, 1 `SiteSettings` (id=1), 1 owner. (Corrected from an earlier draft's arithmetic error — §5's itemized full-menu list totals 37, not 39.)
- Run `seed()` a **second** time on the same session/DB → identical counts, no `IntegrityError`, prices unchanged.
- Change a food's price by hand, re-run `seed()` → price is reset to the seed value (upsert updates mutable fields) — document this as intended.
- Owner already present with a different password → `seed()` does **not** change `hashed_password`.
- The two "Alfredo Pasta" rows exist as separate foods in different categories with prices 600 (thu special) and 550 (house-favourites); likewise "Special Khauasay"/"Special Khousay".

## 8. Deliverables checklist

- [ ] `app/models/*.py` (10 modules + `enums.py` + `__init__.py`)
- [ ] `alembic/versions/0001_core_catalog.py`, `0002_cart_orders_contact.py` (autogenerated + hand-reviewed)
- [ ] `scripts/seed_menu.py` (+ a thin `__main__` that opens a session and calls `seed`)
- [ ] `tests/test_models.py`, `tests/test_seed.py`
- [ ] `conftest.py` factory fixtures filled: `make_category`, `make_food`, `make_addon`
- [ ] (recommended) `conftest.py` switched to `alembic upgrade head`
