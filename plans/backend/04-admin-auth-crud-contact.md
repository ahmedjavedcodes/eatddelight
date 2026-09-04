# 05 — Admin Auth, RBAC, CRUD & Contact Form

**Purpose:** JWT admin authentication, the `owner`/`staff` role system, every admin CRUD endpoint (categories, foods, add-ons, orders, staff, settings), and the contact form (public submit + admin inbox).

**Implements from `backend/CLAUDE.md`:** §6 admin endpoints + `POST /contact`, §7 rule 6 (role-based deletes), §7 rule 7 / §9 (custom-order quoting), §10 (auth & permissions), §13 phases 7, 8, 9.

**Prerequisites:** [02-database-models.md](02-database-models.md) (owner seed, `AdminUser`), [04-orders-and-invoicing.md](04-orders-and-invoicing.md) (order model for admin order management).

**Definition of done:**
- `uv run pytest tests/test_admin_auth.py tests/test_admin_permissions.py tests/test_admin_crud.py tests/test_contact.py` green.
- `ruff` / `mypy` clean.
- Manual: log in as the seeded owner → get access + refresh tokens → create a category as staff (200) → delete it as staff (403) → delete it as owner (204).

---

## 1. `app/core/security.py`

```python
from datetime import datetime, timedelta, timezone
import jwt
from passlib.context import CryptContext
from app.core.config import get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(raw: str) -> str: return _pwd.hash(raw)
def verify_password(raw: str, hashed: str) -> bool: return _pwd.verify(raw, hashed)

def _encode(sub: str, role: str, expires: timedelta, token_type: str) -> str:
    s = get_settings()
    now = datetime.now(tz=timezone.utc)
    payload = {"sub": sub, "role": role, "type": token_type,
               "iat": now, "exp": now + expires}
    return jwt.encode(payload, s.secret_key, algorithm=s.jwt_algorithm)

def create_access_token(user_id: int, role: str) -> str:
    s = get_settings()
    return _encode(str(user_id), role, timedelta(minutes=s.access_token_expire_minutes), "access")

def create_refresh_token(user_id: int, role: str) -> str:
    s = get_settings()
    return _encode(str(user_id), role, timedelta(days=s.refresh_token_expire_days), "refresh")

def decode_token(token: str, *, expected_type: str) -> dict:
    s = get_settings()
    data = jwt.decode(token, s.secret_key, algorithms=[s.jwt_algorithm])   # raises on exp/signature
    if data.get("type") != expected_type:
        raise jwt.InvalidTokenError("wrong token type")
    return data
```

`scripts/seed_menu.py` (plan 02) imports `hash_password` from here — refactor the inline hashing it used as a stopgap.

## 2. `app/api/v1/deps.py` — auth dependencies

```python
from typing import Annotated
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.errors import AuthError, ForbiddenError
from app.core.security import decode_token

bearer = HTTPBearer(auto_error=False)

async def get_current_admin_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUser:
    if creds is None:
        raise AuthError("missing bearer token")
    try:
        data = decode_token(creds.credentials, expected_type="access")
    except jwt.PyJWTError as exc:
        raise AuthError("invalid or expired token") from exc
    user = await db.get(AdminUser, int(data["sub"]))
    if user is None or not user.is_active:
        raise AuthError("account not found or inactive")
    return user

def require_role(*roles: AdminRole):
    async def _dep(user: Annotated[AdminUser, Depends(get_current_admin_user)]) -> AdminUser:
        if user.role not in roles:
            raise ForbiddenError(f"requires role: {', '.join(roles)}")
        return user
    return _dep
```

- `AuthError` → 401 `unauthorized`; `ForbiddenError` → 403 `forbidden` (add both to `app/core/errors.py`).
- **Every admin router declares its roles explicitly** via `dependencies=[Depends(require_role(...))]` or a per-route dep — no implicit "any admin" default (CLAUDE.md §10).

## 3. Auth router — `app/api/v1/admin/auth.py` (prefix `/admin/auth`, tag `admin:auth`)

| Endpoint | Body | Behaviour |
|---|---|---|
| `POST /login` | `{email, password}` | lowercase email, load `AdminUser`, `verify_password`, check `is_active`. Success → `{access_token, refresh_token, token_type: "bearer", user: AdminUserRead}`. Failure → 401 `unauthorized` (same message for bad email and bad password — don't leak which). |
| `POST /refresh` | `{refresh_token}` | `decode_token(..., expected_type="refresh")`, reload user, ensure active → new `{access_token, refresh_token}`. Invalid/expired → 401. |

No logout endpoint (stateless JWT); short access-token TTL covers it. Optional future: a token denylist — out of scope now.

## 4. Admin CRUD routers (`app/api/v1/admin/`)

All under `/admin`, all require a valid admin; role split per CLAUDE.md §1/§7 rule 6/§10. **Create/Update → `owner` + `staff`; Delete → `owner` only** (delete extended to categories & add-ons for consistency — [00 §13](00-overview.md#13-assumptions-being-made-flag-if-any-matter-to-the-client)).

### 4.1 `categories.py` (tag `admin:catalog`)
| Endpoint | Role | Notes |
|---|---|---|
| `GET /admin/categories` | owner, staff | includes inactive; for the admin list |
| `POST /admin/categories` | owner, staff | `CategoryCreate` (name, description, display_order, is_active). Slug auto-generated from name; 409 `slug_conflict` on collision |
| `PUT /admin/categories/{id}` | owner, staff | `CategoryUpdate`; regenerating slug on rename is opt-in (`regenerate_slug: bool = False`) to avoid breaking frontend links |
| `DELETE /admin/categories/{id}` | **owner** | 409 `category_in_use` if it has foods (FK RESTRICT) — surface a clean message, not a raw `IntegrityError` |

### 4.2 `foods.py` (tag `admin:catalog`)
| Endpoint | Role | Notes |
|---|---|---|
| `GET /admin/foods?category_id=&available=&day_of_week=` | owner, staff | admin listing, includes unavailable |
| `POST /admin/foods` | owner, staff | `FoodCreate` — all §4 Food fields; validate `category_id` exists, `price > 0`, `min_order_quantity >= 1`, `day_of_week` only for menu-of-the-day category (warn, don't hard-block, if set elsewhere — client may want ad-hoc specials) |
| `PUT /admin/foods/{id}` | owner, staff | partial update |
| `PATCH /admin/foods/{id}/availability` | owner, staff | `{is_available: bool}` — the common quick toggle |
| `DELETE /admin/foods/{id}` | **owner** | order history is safe (`order_items.food_id` → SET NULL, `food_name` snapshot retained) |

### 4.3 `addons.py` (tag `admin:catalog`)
| Endpoint | Role | Notes |
|---|---|---|
| `GET /admin/addons` | owner, staff | |
| `POST /admin/addons` | owner, staff | `AddOnCreate` (name, price, is_available, is_global). Optional `food_ids: list[int]` to create `food_addons` links when not global |
| `PUT /admin/addons/{id}` | owner, staff | may also replace `food_ids` links |
| `DELETE /admin/addons/{id}` | **owner** | order history safe (`order_item_addons.addon_id` → SET NULL, `addon_name` snapshot retained) |

### 4.4 `orders.py` (tag `admin:orders`)
| Endpoint | Role | Notes |
|---|---|---|
| `GET /admin/orders?status=&order_source=&date_from=&date_to=&q=` | owner, staff | paginated (`limit`/`offset`), newest first; `q` matches `customer_name`/`customer_phone`/`invoice_number` |
| `GET /admin/orders/{id}` | owner, staff | full `OrderRead` + `admin_notes` |
| `PATCH /admin/orders/{id}/status` | owner, staff | `{status: OrderStatus, admin_notes?: str}`. Enforce **forward-only** transitions along `pending→confirmed→preparing→ready→delivered`; `cancelled` allowed from any non-terminal status; reject backward / from-terminal → 409 `invalid_status_transition`. (Transition set is the §14 open question — keep it in one `ALLOWED_TRANSITIONS` dict so it's a one-line change.) |
| `PATCH /admin/orders/{id}/quote` | **owner** | `{subtotal?: Decimal, total: Decimal}` — sets the price on a `custom_request` order (§7 rule 7, §9). 409 `not_a_custom_order` if `order_source != custom_request`. Optionally also advances `status` to `confirmed` if still `pending`. Separate endpoint (recommended) rather than folding into `/status`. |

### 4.5 `staff.py` (tag `admin:staff`) — **owner only** (whole router)
| Endpoint | Notes |
|---|---|
| `GET /admin/staff` | list all `AdminUser`s (owner + staff) |
| `POST /admin/staff` | `{name, email, password}` → creates a `staff` user (role forced to `staff`; an owner is never created here). 409 `email_conflict` |
| `PATCH /admin/staff/{id}` | `{name?, is_active?, password?}` — deactivate instead of delete; cannot deactivate the last active owner (guard); cannot change `role` |

No `DELETE` — deactivation only.

### 4.6 `settings.py` (tag `admin:settings`)
| Endpoint | Role | Notes |
|---|---|---|
| `GET /admin/settings` | owner, staff | returns the full `SiteSettings` (id=1) incl. fields not in the public read |
| `PUT /admin/settings` | **owner** (default) | `SiteSettingsUpdate` — partial. **§14 open question:** whether `staff` may edit About/Contact copy. Keep the role in one `require_role(...)` call so flipping to `owner, staff` is trivial. |

### 4.7 `contact_messages.py` (tag `admin:contact`) — owner, staff
| Endpoint | Notes |
|---|---|
| `GET /admin/contact-messages?is_read=` | paginated, newest first |
| `PATCH /admin/contact-messages/{id}` | `{is_read: bool}` — mark read/unread |

## 5. Contact form — public

`app/api/v1/endpoints/contact.py` (prefix `/contact`, tag `contact`):

| Endpoint | Notes |
|---|---|
| `POST /api/v1/contact` | `ContactMessageCreate` `{name, phone_or_email, message}` (lengths: name ≤120, phone_or_email ≤255, message 1–4000). No auth. Insert `ContactMessage(is_read=False)`. Return 201 `{id, created_at}`. Rate-limited in the hardening pass ([00 §11](00-overview.md#11-phase-1011--hardening--release-checklist)). |

## 6. Schemas

- `app/schemas/auth.py`: `LoginRequest`, `RefreshRequest`, `TokenPair`, `AdminUserRead` (`id, name, email, role, is_active, created_at`).
- `app/schemas/admin.py`: `CategoryCreate/Update`, `FoodCreate/Update`, `AddOnCreate/Update`, `OrderStatusUpdate`, `OrderQuoteUpdate`, `StaffCreate/Update`, `SiteSettingsUpdate`.
- `app/schemas/contact.py`: `ContactMessageCreate`, `ContactMessageRead`.
- Reuse `CategoryRead` / `FoodRead` / `AddOnRead` / `OrderRead` from plans 03–04 for responses.

## 7. Services

- `app/services/auth.py`: `authenticate_admin(session, email, password) -> AdminUser` (raises `AuthError`); `issue_tokens(user) -> TokenPair`.
- `app/services/admin_catalog.py`: create/update/delete for category/food/addon incl. slug generation (`python-slugify` or a small helper), `food_addons` link sync, the `category_in_use` check.
- `app/services/admin_orders.py`: `set_order_status` (with `ALLOWED_TRANSITIONS`), `quote_custom_order`.
- `app/services/staff.py`: `create_staff`, `update_staff` (last-active-owner guard).
- `app/services/contact.py`: `create_contact_message`, `list_contact_messages`, `mark_read`.

## 8. Seed integration (plan 02)

- `scripts/seed_menu.py:seed_owner` uses `app.core.security.hash_password`.
- Only creates an owner when **no** `owner` row exists; never rotates the password. `OWNER_EMAIL` / `OWNER_PASSWORD` / `OWNER_NAME` from `Settings`.
- Document the "first run only" behaviour in the script and README.

## 9. Tests

### `tests/test_admin_auth.py`
- Login as seeded owner → 200, `access_token` + `refresh_token` present, `user.role == "owner"`.
- Wrong password / unknown email → 401, identical body.
- Deactivated user login → 401.
- `get_current_admin_user`: no header → 401; malformed token → 401; expired access token → 401 (freeze/short TTL); refresh token used at `/login`-protected route → 401 (`type` mismatch).
- `POST /refresh` with a valid refresh token → new pair; with an access token → 401; with an expired refresh token → 401.

### `tests/test_admin_permissions.py` (RBAC matrix — the core of CLAUDE.md §7 rule 6)
Parametrized over `(client, endpoint, method) -> expected_status` for `owner_client` and `staff_client`:
- `DELETE /admin/categories/{id}` → owner 204/409, **staff 403**.
- `DELETE /admin/foods/{id}` → owner 204, **staff 403**.
- `DELETE /admin/addons/{id}` → owner 204, **staff 403**.
- `POST/PUT` categories/foods/addons → both 200/201.
- `GET/POST/PATCH /admin/staff` → owner OK, **staff 403** on all.
- `PUT /admin/settings` → owner 200, **staff 403** (until the client says otherwise).
- `PATCH /admin/orders/{id}/quote` → owner 200, **staff 403**.
- `PATCH /admin/orders/{id}/status` → both 200.
- Unauthenticated → 401 on every admin route.

### `tests/test_admin_crud.py`
- Create category (staff) → appears in `GET /admin/categories` and public `GET /categories`.
- Create category with a name that slugifies to an existing slug → 409 `slug_conflict`.
- `DELETE` a category that has foods → 409 `category_in_use` (clean body, not a 500).
- Create food (staff) with bad `category_id` → 422/404; with `price = 0` → 422.
- `PATCH /admin/foods/{id}/availability` flips the public `is_available`.
- Add-on with `is_global=True` then `GET /foods/{id}` (any food) → add-on resolves for it.
- Order status: `pending → confirmed → preparing` OK; `preparing → pending` → 409; `delivered → *` → 409; `* → cancelled` OK from `preparing`.
- `PATCH /admin/orders/{id}/quote` on a custom order → sets `total`, order now shows in `GET /orders/{id}` with the total; on a catalog order → 409 `not_a_custom_order`.
- Staff: create staff (owner) → can log in; deactivate that staff → their token → 401; cannot deactivate the last owner → 409.

### `tests/test_contact.py`
- `POST /api/v1/contact` (no auth) → 201, row stored with `is_read=False`.
- Over-long `message` → 422.
- `GET /admin/contact-messages` (staff) → lists it; `?is_read=false` filter works.
- `PATCH /admin/contact-messages/{id}` `{is_read:true}` → reflected in subsequent GET.
- Unauthenticated `GET /admin/contact-messages` → 401.

## 10. Deliverables checklist

- [ ] `app/core/security.py`
- [ ] `app/api/v1/deps.py`: `get_current_admin_user`, `require_role`
- [ ] `app/api/v1/admin/`: `auth.py`, `categories.py`, `foods.py`, `addons.py`, `orders.py`, `staff.py`, `settings.py`, `contact_messages.py`
- [ ] `app/api/v1/endpoints/contact.py` (public POST)
- [ ] `app/schemas/auth.py`, `admin.py`, `contact.py`
- [ ] `app/services/auth.py`, `admin_catalog.py`, `admin_orders.py`, `staff.py`, `contact.py`
- [ ] `AuthError`, `ForbiddenError`, `CategoryInUseError` (+ `invalid_status_transition`, `slug_conflict`, `not_a_custom_order` codes) in `app/core/errors.py`
- [ ] All admin + contact routers registered in `app/api/v1/router.py`
- [ ] `scripts/seed_menu.py` owner seed wired to `hash_password`
- [ ] `tests/test_admin_auth.py`, `test_admin_permissions.py`, `test_admin_crud.py`, `test_contact.py`
- [ ] `conftest.py`: `owner_user`, `staff_user`, `owner_client`, `staff_client` fixtures
