# 04 — Orders, Checkout & Invoicing

**Purpose:** Order creation from a cart and/or a custom request, all order-time business rules, invoice numbering, the WhatsApp handoff URL, non-enumerable order lookup, and the PDF invoice.

**Implements from `backend/CLAUDE.md`:** §6 (`POST /orders`, `GET /orders/{id}`, `GET /orders/{id}/invoice`), §7 rules 1–5 & 7, §8 (WhatsApp + invoice flow), §9 (custom orders), §13 phases 5 & 6.

**Prerequisites:** [02-database-models.md](02-database-models.md), [03-public-catalog-cart-favourites.md](03-public-catalog-cart-favourites.md).

**Definition of done:**
- `uv run pytest tests/test_orders.py tests/test_invoice.py` green — every §7 rule has a test, incl. the Monday-ordered-on-Monday case.
- `ruff` / `mypy` clean.
- Manual: `POST /api/v1/orders` from a seeded cart returns an `invoice_number`, a working `wa.me` URL, and `GET .../invoice` streams a valid PDF containing the invoice number and total.

---

## 1. Router & files

| File | Prefix | Tag | Endpoints |
|---|---|---|---|
| `app/api/v1/endpoints/orders.py` | `/orders` | `orders` | `POST /`, `GET /{order_id}`, `GET /{order_id}/invoice` |
| `app/services/orders.py` | — | — | order creation, validation, invoice numbering |
| `app/services/whatsapp.py` | — | — | `build_whatsapp_message`, `build_whatsapp_url` |
| `app/services/invoice.py` | — | — | `render_invoice_pdf` |
| `app/services/clock.py` | — | — | `now_pk`, `today_pk`, `earliest_requested_date` (from [00 §6.5](00-overview.md#65-time--advance-ordering)) |
| `app/templates/invoice.html` | — | — | Jinja2 one-pager |

## 2. Schemas (`app/schemas/order.py`)

```python
class OrderItemAddonIn(BaseModel):
    addon_id: int
    quantity: Annotated[int, Field(ge=1)] = 1

class OrderCustomLineIn(BaseModel):          # optional catalog lines on a custom order
    food_id: int
    quantity: Annotated[int, Field(ge=1)]
    notes: str | None = None
    addons: list[OrderItemAddonIn] = []

class OrderCreate(BaseModel):
    customer_name: Annotated[str, Field(min_length=1, max_length=120)]
    customer_phone: Annotated[str, Field(min_length=5, max_length=32)]
    requested_date: date
    order_source: OrderSource = OrderSource.catalog
    # catalog: pull the caller's cart (X-Session-Token). Optionally also accept explicit lines.
    use_cart: bool = True
    lines: list[OrderCustomLineIn] = []
    custom_description: str | None = None

    @model_validator(mode="after")
    def _check_shape(self):
        if self.order_source is OrderSource.custom_request and not self.custom_description:
            raise ValueError("custom_description is required for a custom request")
        return self

class OrderItemAddonRead(BaseModel):
    addon_id: int | None
    name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal

class OrderItemRead(BaseModel):
    id: int
    food_id: int | None
    name: str
    quantity: int
    unit_price: Decimal
    notes: str | None
    addons: list[OrderItemAddonRead]
    line_total: Decimal

class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    invoice_number: str
    customer_name: str
    customer_phone: str
    order_source: OrderSource
    requested_date: date
    status: OrderStatus
    subtotal: Decimal | None
    total: Decimal | None
    is_custom: bool
    custom_description: str | None
    items: list[OrderItemRead]
    created_at: datetime

class OrderCreateResponse(BaseModel):
    order: OrderRead
    invoice_number: str
    lookup_token: str            # returned once, at creation, for the frontend to store
    whatsapp_url: str
    invoice_url: str             # f"{api_v1_prefix}/orders/{id}/invoice?token=..."
```

## 3. `POST /api/v1/orders`

Header: `X-Session-Token` (required when `use_cart=True`).

**Flow (in one DB transaction):**
1. If `order_source == catalog` and `use_cart`: load the caller's cart; combine its items with any explicit `lines`. If `order_source == custom_request`: `lines` may be empty.
2. Build the working line list `[(food, quantity, notes, [(addon, qty), ...]), ...]`.
3. **Rule 4 — availability** (re-checked now, not trusted from cart): every `food.is_available` and every `addon.is_available` must be `True` → else `UnavailableItemError` (409).
4. **Rule 3 — min quantity**: `quantity >= food.min_order_quantity` for every line → else `MinQuantityError` (422).
5. **Rule 1 — advance ordering**: `requested_date >= earliest_requested_date()` (tomorrow in Asia/Karachi) → else `AdvanceOrderError` (422, message includes the earliest allowed date). Applies to `catalog` and `custom_request` alike.
6. **Rule 2 — day-of-week specials**: for every line whose `food.day_of_week` is set, `requested_date.weekday()` must equal that day's index (`mon=0 … fri=4`). Combined with rule 1, if today is Monday and the cart holds Monday's special, the earliest valid `requested_date` is **next Monday** (tomorrow fails rule 2). → else `DayOfWeekMismatchError` (422, message: `"Makhni Handi ... is only available on Monday; the earliest date is 2026-09-08."`).
7. **Rule 5 — price snapshot**: for each line, copy `unit_price = food.price` and, per add-on, `unit_price = addon.price`, plus `food_name` / `addon_name` snapshots, into `OrderItem` / `OrderItemAddon`. Never reference live prices afterward.
8. Compute `subtotal = Σ line_total` using the **same convention as the cart** ([03 §5.3](03-public-catalog-cart-favourites.md#53-line-total-maths-used-to-build-cartread-live-prices)): `line_total = unit_price*qty + Σ(addon.unit_price * addon.qty * line.qty)`.
9. `total`:
   - `catalog` → `total = subtotal`.
   - `custom_request` → `subtotal` and `total` left `NULL` (owner quotes later via plan 05). Even if custom lines are present, keep `total` `NULL` until quoted (owner may bundle a bespoke item priced offline) — **decision**, note it in code; alternative (set `total = subtotal` when custom lines exist) is acceptable if the client prefers.
10. **Rule 7 / §9 — empty order guard**: a `catalog` order with zero resulting lines → `EmptyOrderError` (422). A `custom_request` with zero lines is allowed (relies on `custom_description`).
11. Generate `invoice_number` (§4) and `lookup_token = secrets.token_urlsafe(16)`.
12. Persist `Order` (+ `is_custom = order_source is custom_request`), `OrderItem`s, `OrderItemAddon`s.
13. If created from the cart: **clear the cart** (`delete` its items) — [00 §13](00-overview.md#13-assumptions-being-made-flag-if-any-matter-to-the-client).
14. Build `whatsapp_url` (§5) and `invoice_url`; return `OrderCreateResponse` (201).

## 4. Invoice numbering — `services/orders.py:next_invoice_number`

Format: `DD-YYYYMMDD-NNNN` where `YYYYMMDD` is **today in Asia/Karachi** and `NNNN` is a zero-padded per-day counter starting at `0001`.

**Recommended approach — count + unique constraint + retry:**
```python
async def next_invoice_number(session) -> str:
    day = today_pk().strftime("%Y%m%d")
    prefix = f"DD-{day}-"
    count = await session.scalar(
        select(func.count()).select_from(Order).where(Order.invoice_number.like(f"{prefix}%"))
    )
    return f"{prefix}{count + 1:04d}"
```
Call it inside the order transaction; `uq_orders_invoice_number` is the race backstop. On `IntegrityError` for that constraint, retry the whole numbering+insert **once** (recompute count). Two concurrent orders on the same day is the realistic worst case for a single home kitchen — one retry is enough.

**Alternative (documented, not chosen):** a `daily_sequences(day date pk, last_value int)` table updated with `SELECT ... FOR UPDATE`. More robust under high concurrency, unnecessary here.

## 5. WhatsApp handoff — `services/whatsapp.py`

```python
def build_whatsapp_message(order: Order, settings: SiteSettings) -> str: ...
def build_whatsapp_url(order: Order, settings: SiteSettings) -> str:
    from urllib.parse import quote
    return f"https://wa.me/{settings.whatsapp_number}?text={quote(build_whatsapp_message(order, settings))}"
```

**Message format** (plain text, `\n` separated):
```
Daughter's Delight — New Order
Invoice: DD-20260904-0001
Name: Ayesha Khan
Phone: 0300-1234567
Requested for: Mon, 08 Sep 2026

Items:
- 3 x Chicken Biryani @ 400 = 1200
    + 3 x Extra Raita @ 50 = 150
- 3 x Peas Pulao @ 300 = 900

Subtotal: PKR 2250
Total: PKR 2250
```
- For `custom_request`: after the header block, add `Custom request:\n<custom_description>` and, if `total is None`, print `Total: to be confirmed`.
- Numbers formatted with no decimals when integral, else 2 dp. Currency label `PKR`.
- `whatsapp_number` comes from `SiteSettings` (fallback to `settings.whatsapp_number` env if the row is somehow missing).

## 6. `GET /api/v1/orders/{order_id}?token=<lookup_token>` → `OrderRead` (+ `whatsapp_url`, `invoice_url`)

- `token` query param **required**. If missing or not matching the row's `lookup_token` → **404** (`not_found`) — never 403, never reveal existence. Same 404 for an unknown `order_id`.
- Returns the full `OrderRead`. This is the order-confirmation lookup the frontend hits after checkout and on a shared confirmation link.
- Optional: `POST /api/v1/orders/{order_id}/whatsapp-sent?token=` to stamp `whatsapp_link_sent_at` (frontend analytics). Low priority — include only if trivial.

## 7. `GET /api/v1/orders/{order_id}/invoice?token=<lookup_token>` → PDF

- Same token check → 404 on mismatch.
- `render_invoice_pdf(order, settings)` in `services/invoice.py`:
  - Render `app/templates/invoice.html` with Jinja2 (`order`, `settings`, computed line rows, `generated_at`).
  - `weasyprint.HTML(string=html).write_pdf()` — run in a threadpool (`await anyio.to_thread.run_sync(...)` / `run_in_threadpool`) since WeasyPrint is blocking.
  - Return `Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{order.invoice_number}.pdf"'})`.
- **Template contents:** business name + tagline (logo optional, from a static asset if provided later), `Invoice #`, invoice date + requested date, customer name/phone, a line-item table (item, qty, unit price, line total; add-ons as indented sub-rows), subtotal, total (or "To be confirmed"), footer `"Homemade Made with Love"` + contact phone/Instagram from `SiteSettings`.
- **WeasyPrint fallback:** if its system libs (Pango/Cairo/GDK-PixBuf) are unavailable in the target environment, swap `render_invoice_pdf` for a `reportlab` implementation behind the same signature. Keep the HTML template regardless (useful for an HTML invoice preview endpoint later). Note this in the module docstring.

## 8. Custom orders (§9)

- `order_source = custom_request`, `custom_description` required, catalog `lines` optional.
- Lands in the admin queue as `status = pending`, `total = NULL`.
- Owner reviews, coordinates price over WhatsApp/phone (outside the system), then sets `total` + advances `status` via plan 05's `PATCH /admin/orders/{id}/quote` and `/status`.
- No automated quoting. `POST /orders` still runs rules 1 (advance date) and, if custom lines reference day-of-week foods, rule 2.

## 9. Tests

### `tests/test_orders.py`
Use a `clock` fixture that monkeypatches `app.services.clock.now_pk` to a fixed Asia/Karachi datetime.

- **Rule 1:** `requested_date = today_pk()` → 422 `advance_order_required`; `= today_pk() + 1 day` → OK (non-weekly cart).
- **Rule 1 boundary:** freeze clock at `2026-09-07 23:30 Asia/Karachi`; `requested_date = 2026-09-08` passes, `2026-09-07` fails.
- **Rule 2 — Monday on Monday:** freeze clock to a Monday; cart holds Monday's special; `requested_date = tomorrow` (Tuesday) → 422 `day_of_week_mismatch`; `requested_date = next Monday` → OK. Assert the error message names the earliest valid date.
- **Rule 2 mixed cart:** Monday special + a full-menu item, `requested_date` = a Monday ≥ tomorrow → OK.
- **Rule 3:** line `quantity = 2` for a `min_order_quantity = 3` food → 422 `min_quantity`.
- **Rule 4:** food flipped `is_available = False` after it was added to cart → 409 `item_unavailable` at order time.
- **Rule 5 — snapshot:** create order; then change `Food.price`; reload the order → `OrderItem.unit_price` unchanged; `subtotal`/`total` unchanged.
- **Rule 7 / empty:** `catalog` order with an empty cart and no `lines` → 422 `empty_order`.
- **Custom:** `order_source = custom_request`, only `custom_description` → 201, `total is None`, appears with `status = pending`.
- **Invoice number:** two orders same frozen day → `DD-<day>-0001`, `DD-<day>-0002`; both unique. Simulate a collision (pre-insert `DD-<day>-0001`) → creation still succeeds via the retry, yields `0002`.
- **Cart cleared:** after a successful catalog order, `GET /cart` for that token is empty.
- **WhatsApp:** `build_whatsapp_message` output matches an expected string fixture (locks item/add-on lines, subtotal, total); `build_whatsapp_url` starts `https://wa.me/923122252915?text=` and round-trips via `urllib.parse.unquote` back to the message.
- **Lookup:** `GET /orders/{id}` without `token` → 404; with wrong token → 404; with correct token → 200 and matches created order.

### `tests/test_invoice.py`
- `GET /orders/{id}/invoice?token=<good>` → 200, `Content-Type: application/pdf`, body starts with `%PDF-`, `Content-Disposition` filename is the invoice number.
- Extract text (pypdf) → contains invoice number, customer name, each food name, and `Total` (or `To be confirmed` for an unpriced custom order).
- Wrong/absent token → 404.
- (If reportlab fallback is active) same assertions hold.

## 10. Deliverables checklist

- [ ] `app/schemas/order.py`
- [ ] `app/services/clock.py`, `orders.py`, `whatsapp.py`, `invoice.py`
- [ ] `app/templates/invoice.html`
- [ ] `app/api/v1/endpoints/orders.py` + registered in router
- [ ] Concrete `AdvanceOrderError`, `DayOfWeekMismatchError`, `EmptyOrderError` in `app/core/errors.py`
- [ ] `tests/test_orders.py`, `tests/test_invoice.py`
- [ ] `conftest.py`: `clock` fixture (freeze `now_pk`), `make_order` factory, `pypdf` dev dep for invoice text assertions
