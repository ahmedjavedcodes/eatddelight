# 03 — Public Catalog, Cart & Favourites APIs

**Purpose:** All unauthenticated read endpoints for the storefront (settings, categories, menu, weekly menu, foods + filters) plus the session-token-scoped cart and favourites, including add-to-cart validation.

**Implements from `backend/CLAUDE.md`:** §6 public endpoints (settings, categories, menu, weekly-menu, foods, cart, favourites), §7 rules 3 & 4 (min qty, availability) at cart-write time, §8 session-token handling, §13 phases 3 & 4.

**Prerequisites:** [02-database-models.md](02-database-models.md).

**Definition of done:**
- `uv run pytest tests/test_menu.py tests/test_cart.py tests/test_favourites.py` green.
- `ruff` / `mypy` clean.
- Manual: with the seed loaded, `GET /api/v1/menu` returns 10 full-menu categories with foods; `GET /api/v1/weekly-menu` returns exactly 5 specials Mon→Fri.

---

## 1. Routers & files

| Router file | Prefix | Tag | Endpoints |
|---|---|---|---|
| `app/api/v1/endpoints/settings.py` | `/settings` | `settings` | `GET /` |
| `app/api/v1/endpoints/categories.py` | `/categories` | `catalog` | `GET /`, `GET /{category_id}/foods` |
| `app/api/v1/endpoints/menu.py` | `` | `catalog` | `GET /menu`, `GET /weekly-menu` |
| `app/api/v1/endpoints/foods.py` | `/foods` | `catalog` | `GET /`, `GET /{food_id}` |
| `app/api/v1/endpoints/cart.py` | `/cart` | `cart` | `GET /`, `POST /`, `POST /items`, `PATCH /items/{item_id}`, `DELETE /items/{item_id}` |
| `app/api/v1/endpoints/favourites.py` | `/favourites` | `favourites` | `GET /`, `POST /`, `DELETE /{food_id}` |

Register all six in `app/api/v1/router.py`.

## 2. Schemas (`app/schemas/`)

### `settings.py`
```python
class SiteSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    business_name: str
    tagline: str | None
    about_text: str | None
    contact_phone: str
    whatsapp_number: str
    instagram_handle: str
    address: str | None
    opening_hours: str | None
```

### `catalog.py`
```python
class AddOnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    price: Decimal
    is_available: bool
    is_global: bool

class FoodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category_id: int
    name: str
    description: str | None
    price: Decimal
    image_url: str | None
    is_available: bool
    min_order_quantity: int
    is_single_serving: bool
    requires_advance_order: bool
    day_of_week: DayOfWeek | None

class FoodDetailRead(FoodRead):
    addons: list[AddOnRead]          # resolved: global ∪ food-specific, deduped

class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    description: str | None
    display_order: int

class CategoryWithFoods(CategoryRead):
    foods: list[FoodRead]

class WeekdayGroup(BaseModel):
    day_of_week: DayOfWeek
    food: FoodRead
```

### `cart.py`
```python
class CartItemAddonIn(BaseModel):
    addon_id: int
    quantity: Annotated[int, Field(ge=1)] = 1

class CartItemCreate(BaseModel):
    food_id: int
    quantity: Annotated[int, Field(ge=1)]
    notes: Annotated[str, Field(max_length=300)] | None = None
    addons: list[CartItemAddonIn] = []

class CartItemUpdate(BaseModel):
    quantity: Annotated[int, Field(ge=1)] | None = None
    notes: Annotated[str, Field(max_length=300)] | None = None
    addons: list[CartItemAddonIn] | None = None      # full replace when present

class CartItemAddonRead(BaseModel):
    addon_id: int
    name: str
    quantity: int
    unit_price: Decimal          # live price
    line_total: Decimal

class CartItemRead(BaseModel):
    id: int
    food_id: int
    name: str
    quantity: int
    notes: str | None
    unit_price: Decimal          # live food price
    addons: list[CartItemAddonRead]
    line_total: Decimal          # (food unit_price * qty) + sum(addon line_total * item qty?) — see §5.3

class CartRead(BaseModel):
    id: int
    session_token: str
    items: list[CartItemRead]
    subtotal: Decimal
    item_count: int
```

### `favourite.py`
```python
class FavouriteCreate(BaseModel):
    food_id: int

class FavouriteRead(BaseModel):
    food: FoodRead
    created_at: datetime
```

## 3. Endpoint specs

### 3.1 `GET /api/v1/settings` → `SiteSettingsRead`
Load `SiteSettings` id=1. If missing (seed not run) → 404 `{"code":"not_found"}`. Read-only, no auth.

### 3.2 `GET /api/v1/categories?active=true&include=menu-of-the-day` → `list[CategoryRead]`
- Default: `is_active = True`, ordered by `display_order, name`.
- **Decision (per CLAUDE.md §6 note):** keep "Menu of the Day" in this list by default; callers that want only à la carte pass `?exclude_weekly=true` (server filters `slug != 'menu-of-the-day'`). Do **not** add a `kind` column.

### 3.3 `GET /api/v1/categories/{category_id}/foods?available=` → `list[FoodRead]`
Foods for the category, ordered by `name`. `available` filter optional (default: all). 404 if category missing/inactive.

### 3.4 `GET /api/v1/menu` → `list[CategoryWithFoods]`
Full à la carte menu grouped by category, for the `/menu` page.
- Query: active categories where `slug != 'menu-of-the-day'` (equivalently, only include foods with `day_of_week IS NULL`), each with its available-or-all foods ordered by name, categories ordered by `display_order`.
- One query with `selectinload(Category.foods)`; filter empty categories out.

### 3.5 `GET /api/v1/weekly-menu` → `list[WeekdayGroup]`
The 5 daily specials, for the `/weekly-menu` page.
- Query: `select(Food).where(Food.day_of_week.is_not(None))` ordered by a `CASE` on the enum (`mon,tue,wed,thu,fri`).
- Return one `WeekdayGroup` per weekday that has a special. If a day has none, omit it (don't fabricate). If a day somehow has >1, return the first by `id` and log a warning (seed guarantees exactly one).

### 3.6 `GET /api/v1/foods/{food_id}` → `FoodDetailRead`
- Load the food; 404 if missing.
- **Resolved add-ons** = `resolve_addons_for_food(session, food)` (service, §5.1): union of all `AddOn` with `is_global = True` and the food's explicit `food_addons` links, deduped by `id`, only `is_available = True`, ordered by name.
- Returns even when `is_available = False` (frontend shows it greyed) — filtering is via the list endpoint's `available` param.

### 3.7 `GET /api/v1/foods?search=&category_id=&day_of_week=&available=` → `list[FoodRead]`
Filters (all optional, AND-combined):
- `search` → `name ILIKE %term%` OR `description ILIKE %term%`.
- `category_id` → exact.
- `day_of_week` → exact enum; pass `day_of_week=null`/omit for à la carte only? Keep simple: if provided, `Food.day_of_week == value`.
- `available` → `is_available == bool(value)`.
- Ordering: `name`. Pagination: `limit` (default 100, max 200), `offset`. Used by the frontend search box and menu filtering.

### 3.8 Cart endpoints — all require `X-Session-Token` header (`get_session_token` dep)

| Method / path | Body | Behaviour |
|---|---|---|
| `GET /cart` | — | `get_or_create_cart(token)` → `CartRead` with live-priced lines |
| `POST /cart` | — | same as GET (explicit get-or-create); 200 with `CartRead` |
| `POST /cart/items` | `CartItemCreate` | validate (§5.2) → add line (merge into existing line for same `food_id` + identical notes? **No** — always a new line; simpler and matches "notes per line"). Returns `CartRead` |
| `PATCH /cart/items/{item_id}` | `CartItemUpdate` | item must belong to the caller's cart (else 404). Re-validate qty/availability. `addons` when present fully replaces the line's add-ons. Returns `CartRead` |
| `DELETE /cart/items/{item_id}` | — | 404 if not in caller's cart; else remove, return `CartRead` (200) |

No "delete cart" endpoint — carts are cheap and cleared on successful order (plan 04).

### 3.9 Favourites endpoints — all require `X-Session-Token`

| Method / path | Body | Behaviour |
|---|---|---|
| `GET /favourites` | — | list `FavouriteRead` for the token, newest first; each embeds the `FoodRead` |
| `POST /favourites` | `FavouriteCreate` | insert `(token, food_id)`; if the pair already exists → **200, no error** (idempotent; catch `IntegrityError` or pre-check). 404 if `food_id` unknown |
| `DELETE /favourites/{food_id}` | — | delete the pair if present; 204 whether or not it existed (idempotent) |

## 4. Session-token dependency

From [01 §6](01-fastapi-scaffolding.md#6-appapiv1depspy-stubs-for-this-phase): `get_session_token` reads `X-Session-Token` (`Header(min_length=1)`). Missing/empty → FastAPI 422 via the standard validation handler. No further validation; it is only a lookup key (CLAUDE.md §8).

## 5. Services (`app/services/`)

### 5.1 `catalog.py`
```python
async def resolve_addons_for_food(session, food) -> list[AddOn]:
    """Global add-ons ∪ this food's explicit links, available only, deduped, name-ordered."""
```
One query: `select(AddOn).where(or_(AddOn.is_global.is_(True), AddOn.id.in_(select(food_addons.c.addon_id).where(food_addons.c.food_id == food.id)))).where(AddOn.is_available.is_(True)).order_by(AddOn.name)`.

### 5.2 `cart.py`
```python
async def get_or_create_cart(session, session_token: str) -> Cart: ...
async def add_cart_item(session, cart: Cart, payload: CartItemCreate) -> Cart: ...
async def update_cart_item(session, cart: Cart, item_id: int, payload: CartItemUpdate) -> Cart: ...
async def remove_cart_item(session, cart: Cart, item_id: int) -> Cart: ...
```

**Validation applied on add/update (CLAUDE.md §7 rules 3–4):**
1. Food exists → else 404.
2. `food.is_available` is `True` → else `UnavailableItemError` (409, `item_unavailable`).
3. `payload.quantity >= food.min_order_quantity` → else `MinQuantityError` (422, `min_quantity`, message names the min, e.g. `"Chicken Biryani requires a minimum of 3."`).
4. Every referenced add-on exists, is `is_available`, and is resolvable for the food (global or linked) → else `UnavailableItemError`.
- **Not enforced at cart time:** day-of-week matching and advance-date rules — those are order-time only (state this in a code comment; tested in plan 04).

### 5.3 Line-total maths (used to build `CartRead`, live prices)
- `item.unit_price` = current `food.price`.
- add-on `line_total` = `addon.price * addon.quantity` (add-on quantity is per unit of the item; **decision:** multiply by item quantity too → effective add-on cost = `addon.price * addon.quantity * item.quantity`). Document the chosen convention in the schema docstring and mirror it exactly in plan 04's order snapshotting so cart total == order subtotal.
- `item.line_total` = `food.price * item.quantity + Σ(addon.price * addon.quantity * item.quantity)`.
- `cart.subtotal` = `Σ item.line_total`; `item_count` = `Σ item.quantity`.

### 5.4 `favourites.py`
```python
async def list_favourites(session, token) -> list[Favourite]: ...
async def add_favourite(session, token, food_id) -> Favourite | None:  # None if already existed
async def remove_favourite(session, token, food_id) -> None: ...
```

## 6. Tests

### `tests/test_menu.py`
- `GET /settings` returns seeded business info; 404 when no row.
- `GET /categories` returns 11 seeded categories ordered by `display_order`; `?exclude_weekly=true` returns 10 (no `menu-of-the-day`).
- `GET /categories/{id}/foods` returns that category's foods; 404 for unknown id.
- `GET /menu`: 10 groups, none is "Menu of the Day", every group non-empty, "House Favourites" contains "Alfredo Pasta" @ 550.
- `GET /weekly-menu`: exactly 5 groups, order `mon..fri`, Thursday's `food.name` is "Alfredo Pasta with Sauce" @ 600 (proves the deliberate duplicate is separate).
- `GET /foods?search=biryani` matches "Chicken Biryani" (full menu) and "Chicken Biryani with Raita + Salad" (Friday special); `?day_of_week=fri` returns only the Friday special; `?category_id=` + `?available=false` filters combine.
- `GET /foods/{id}` on a food with a global add-on + a specific add-on returns both, once each, available only.

### `tests/test_cart.py`
- No `X-Session-Token` → 422.
- `GET /cart` twice with the same token → same cart id (get-or-create), empty.
- Two different tokens → isolated carts.
- `POST /cart/items` with `quantity = min_order_quantity - 1` → 422 `min_quantity`; with `= min_order_quantity` → 200, line present.
- `POST /cart/items` for an unavailable food → 409 `item_unavailable`.
- `POST /cart/items` with an add-on not valid for the food → 409.
- `CartRead.subtotal` equals hand-computed total for a 2-line cart with add-ons (locks the §5.3 convention).
- `PATCH` another token's item id → 404. `DELETE` another token's item id → 404.
- `PATCH` with `addons: []` clears the line's add-ons.

### `tests/test_favourites.py`
- `POST /favourites` then `POST` again same food → both 200, `GET` shows one entry.
- `POST` unknown food → 404.
- `DELETE /favourites/{food_id}` twice → both 204.
- Favourites are token-scoped (other token sees none).

## 7. Deliverables checklist

- [ ] `app/schemas/settings.py`, `catalog.py`, `cart.py`, `favourite.py`
- [ ] `app/services/catalog.py`, `cart.py`, `favourites.py`
- [ ] `app/api/v1/endpoints/settings.py`, `categories.py`, `menu.py`, `foods.py`, `cart.py`, `favourites.py`
- [ ] Routers registered in `app/api/v1/router.py`
- [ ] Concrete `MinQuantityError`, `UnavailableItemError` in `app/core/errors.py`
- [ ] `tests/test_menu.py`, `tests/test_cart.py`, `tests/test_favourites.py`
- [ ] `conftest.py`: `session_client` helper that sets `X-Session-Token`, `seeded_db` fixture
