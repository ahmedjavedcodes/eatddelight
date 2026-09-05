# Daughter's Delight — Website Architecture (Structure → Brand Mapping)

**Brand guidelines source:** `brand/design/design.md` (extracted from Instagram @eatddelight, 2026-09-04)
**Reference layout source:** `brand/theme/image.png` ("TasteHaven" food-delivery homepage screenshot)

This document maps the **structural pattern** of the TasteHaven reference homepage onto Daughter's Delight's brand tokens, section by section, in the order the sections appear. TasteHaven's own colors, fonts, and imagery are discarded entirely — only its layout skeleton (nav pattern, hero split, card grids, section order, footer structure) is kept.

Several TasteHaven sections assume capabilities eatddelight's backend doesn't have (accounts, online checkout/discounts, blog, newsletter, multi-location footer links). Each of those is flagged inline with a proposed in-scope substitute rather than silently carried over — see the **Notes** line in each block, and the summary of judgment calls at the end.

---

### 1. Top Navigation
**Structure (from reference):** Logo left · horizontal nav links center · icon cluster + primary CTA button right. Sticky/fixed on scroll (implied by the reference's persistent header treatment).
**Applied brand tokens:**
- Background: `secondary` (#FFFFFF)
- Logo: circular pink badge mark + "Daughter'sDelight" wordmark, per the logo description in `design.md` — sized to the reference's compact header logo lockup, adequate clear space around the circular badge
- Nav links: body font (system sans, per `design.md` — unconfirmed, flag if client supplies a real brand font later), `text` (#1A1A1A), hover/active state in `primary` (#E91E8C)
- Primary CTA button: `primary` fill, white text, `radius: lg` (rounded pill/rounded-rect, matching the brand's soft/curved shape language)
- Active nav-item underline (reference shows a green underline on "Home"): rendered in `primary` pink instead
**Notes:** Reference nav is `Home / Menu / Catering / About Us / Blog / Contact` + account icon + cart icon + "Order Now" button. eatddelight's actual scope (per `frontend/CLAUDE.md`) is `Home / Weekly Menu / Menu / About / Contact` with no user accounts and no blog. Proposed nav: **Home · Weekly Menu · Menu · About · Contact**, icon cluster **Favourites (heart) · Cart**, no account icon (there are no customer accounts), CTA button reads **"View Menu"** or **"Order on WhatsApp"** rather than "Order Now" (there's no in-app checkout completion — checkout hands off to WhatsApp). The reference's "Catering" nav item structurally maps well to eatddelight's existing **custom/bespoke order request** flow — consider a "Custom Orders" nav item or fold it into `/checkout` rather than dropping the concept entirely.

### 2. Hero
**Structure (from reference):** Two-column split. Left: small eyebrow label, large two-line headline (second line in an accent color), supporting subtext, two CTA buttons (solid + outline-with-icon), a row of 4 small icon+label trust badges below. Right: large circular-cropped food photo with a small floating card overlapping its lower-right edge (avatar cluster + rating number).
**Applied brand tokens:**
- Background: `secondary` (#FFFFFF)
- Eyebrow label: `primary` pink, small caps, per the bold/playful heading treatment in `design.md`
- Headline: heading font (rounded geometric sans — Poppins/Baloo/Fredoka category per `design.md`), `text` color for line 1, `primary` pink for the accent line (mirrors reference's green accent word)
- Subtext: body font, `text` at reduced opacity/gray per "comfortable spacing" tone
- Primary CTA button: `primary` fill, `radius: lg`; secondary CTA: outline button, `primary` border/text on `secondary` background
- Trust-badge icons: simple line icons, `primary` or near-black, `radius: lg` soft container if boxed
- Hero image: top-down or 3/4-angle food photography per `design.md`'s imagery style (not the reference's own photo) — circular or soft-rounded crop to match the brand's curved shape language
- Floating rating card: white card, `radius: lg`, soft shadow, star color in `primary` or a warm gold (guidelines don't specify a star-rating color — using gold as a common, low-risk default; flag for client confirmation)
**Notes:** The 4 trust-badge labels ("Fresh Ingredients / Expert Chefs / Fast Delivery / 100% Quality") are TasteHaven-specific copy, not brand tokens — content, not styling. Reasonable in-scope substitutes given eatddelight's actual model: **"Fresh, Homemade" / "1-Day Advance Order" / "Made With Love" / "Available Daily"**, but this is copywriting and should be confirmed with the client rather than treated as settled. The floating "4.8k Happy Customers" rating card assumes a review/ratings system — **no such data model exists in the backend** (Section 4 of `backend/CLAUDE.md` has no reviews table). Either treat this as static, manually-updated marketing content, or drop it until/unless the client wants a review feature scoped.

### 3. Popular Dishes (Card Grid)
**Structure (from reference):** Eyebrow label + heading left, "View Full Menu →" link right, same row. Below: 4-column card grid. Each card: square-ish food photo with a heart/wishlist icon top-right overlay, item name, one-line description, price left + circular "+" add-to-cart button bottom-right.
**Applied brand tokens:**
- Background: `secondary` (#FFFFFF)
- Section heading: heading font, `text`, eyebrow in `primary`
- "View Full Menu" link: `primary` pink, body font
- Card container: white, `radius: lg`, soft shadow — matches the "clear white cards/sections" density pattern noted in `design.md`
- Wishlist heart icon: outline by default, filled `primary` pink on active/favourited state
- Item name: heading font (smaller weight) or bold body font, `text`
- Description: body font, muted `text`
- Price: bold, `text` or `primary`
- Add button: solid `primary` circle, white "+" icon, `radius: full`
**Notes:** This section maps almost 1:1 onto eatddelight's real **"Our Most Loved Dishes" → link to `/menu`** pattern, and the heart icon is a direct match for the already-planned client-side **Favourites** feature (Section 4/6 of `frontend/CLAUDE.md`). The circular "+" button maps directly to "add to cart." No gaps here — this is the cleanest structural fit in the whole reference.

### 4. Promo / Offer Banner
**Structure (from reference):** Full-width dark banner, background food photo with dark overlay. Left: small eyebrow, large headline, subtext, one CTA button. Right: circular badge with large percentage-off text and a dashed-circle border, small decorative arrow.
**Applied brand tokens:**
- Background: dark overlay in `text` near-black (#1A1A1A) at high opacity over a food photo, OR — given the brand's "not moody/dark" imagery tone note in `design.md` — an alternative treatment using a solid `primary` pink background instead of a dark photo overlay, to stay consistent with the bright/appetizing tone rather than introducing a moody dark section that doesn't appear anywhere else in the brand guidelines
- Headline: heading font, white text on `primary` (or white on dark overlay if the photo-banner version is kept)
- CTA button: white fill, `primary` text (inverted from the standard button, for contrast against the pink/dark band)
- Circular badge: white circle, `primary` text, dashed border in white or a light tint
**Notes:** **Flag — no discount/coupon system exists in the backend** (there's no pricing-adjustment or promo-code concept anywhere in `backend/CLAUDE.md`'s domain model). "20% Off Your First Order" doesn't map to any real business capability. Propose repurposing this exact structural slot for something eatddelight *does* have: a **"Menu of the Day" spotlight band** — same layout (eyebrow + headline + CTA left, a circular badge right showing e.g. today's weekday + special name instead of a percentage), linking to `/weekly-menu`. This keeps the reference's visual rhythm (a bold interruptive band between grid sections) while only advertising a real thing.

### 5. Testimonials
**Structure (from reference):** Eyebrow + heading left, "View All Reviews →" link right. 3-column card grid: quote mark icon, 2-3 line quote text, avatar photo + name + city, star rating row. Prev/next arrow controls below/beside the grid (carousel implied).
**Applied brand tokens:**
- Background: `secondary` or a very light neutral tint (guidelines don't define a card/section background distinct from white — using a subtle off-white, e.g. `#FFF8FB`-range pink-tinted neutral, as a soft derivation from the primary pink per the "comfortable" spacing/tone note; flag for client confirmation since it's not a defined token)
- Quote icon: `primary` pink, light weight
- Quote text: body font, `text`
- Name: bold body font, `text`; city: muted body font
- Star rating: gold/yellow (same flag as Section 2 — not a defined brand token)
- Carousel arrows: circular buttons, `primary` outline or fill
**Notes:** Same gap as the hero's rating card — **no testimonials/reviews data model exists yet**. This section can only ship as static, manually-curated content (the owner supplies a handful of quotes) rather than anything backend-driven, unless a reviews feature gets scoped later.

### 6. Latest Articles / Blog
**Structure (from reference):** Eyebrow + heading left, "View All Articles →" link right. 3-column card grid: image, small date + category meta line, title, "Read More →" link.
**Applied brand tokens:**
- Card: white, `radius: lg`, image top with rounded top corners
- Meta line: small, muted `text`, `primary` for the category label
- Title: heading font, `text`
- "Read More" link: `primary`
**Notes:** **Flag — blog/recipe content is explicitly out of scope** for eatddelight (`backend/CLAUDE.md` Section 3 lists content/blog features as non-goals unless the client asks later, and there's no CMS/article model in the domain). Two options: (a) drop this section entirely, or (b) repurpose the same card-grid structure as a lightweight **"From Our Kitchen" Instagram feed strip** (pulling recent @eatddelight posts, or simply linking out to Instagram) — since the brand's actual content presence lives on Instagram already, per `design.md`. Recommend (b) if the client wants this slot filled, but this needs client confirmation before building either way.

### 7. Newsletter / Signup Band
**Structure (from reference):** Full-width light band. Left: icon + "Stay Updated" heading + subtext. Right: email input field + solid "Subscribe" button, inline.
**Applied brand tokens:**
- Background: light warm neutral (soft pink tint off `primary`, per the same "no defined light-band token" gap as Section 5)
- Icon: `primary` circle with white icon
- Heading: heading font, `text`
- Input field: white, `radius: lg`, border in light gray or a pink-tinted border
- Button: `primary` fill, white text, `radius: lg`
**Notes:** **Flag — no email/newsletter capture exists in the backend** (`ContactMessage` is a one-off contact form submission, not a subscription list — see `backend/CLAUDE.md` Section 4). Given the business's actual conversion channel is WhatsApp/phone (not email), propose repurposing this exact band as a **"Order on WhatsApp" strip** instead — same layout (icon + heading + subtext left, one prominent button right), but the button opens the WhatsApp chat link rather than submitting an email. This is a much closer fit to how the business actually operates.

### 8. Footer
**Structure (from reference):** Dark full-width footer. Column 1: logo + tagline + social icons. Columns 2-4: link lists under headings ("Quick Links", "Support", "Information"). Column 5: contact block (address, phone, email, hours). Bottom bar: copyright line.
**Applied brand tokens:**
- Background: `text` near-black (#1A1A1A) — this is the one place a dark background is well-supported by the guidelines (body text color repurposed as a dark surface), unlike Section 4's banner
- Logo lockup: white version of the circular pink-badge mark (or full-color badge on the dark field — the pink badge itself already has enough contrast against near-black)
- Column headings: heading font, white, small-caps or bold
- Links: body font, light gray, `primary` pink on hover
- Social icons: outline icons, white, `primary` on hover — maps directly to the Instagram-first presence in `design.md`
- Contact block: sourced live from `SiteSettings` (phone, WhatsApp number, Instagram handle, address, opening hours — all already modeled in `backend/CLAUDE.md` Section 4)
- Bottom bar: divider line in a low-opacity white, centered copyright text
**Notes:** Reference's column links (`Careers`, `Franchise`, `Shipping & Delivery`, `Returns`, `Terms & Conditions`) assume a multi-location e-commerce business — **eatddelight is a single home-kitchen with no shipping, no franchise, no accounts**, so most of these don't apply. Proposed replacement columns: **Quick Links** (Home / Weekly Menu / Menu / About / Contact), **Get in Touch** (WhatsApp button, phone number, Instagram link — all from `SiteSettings`), dropping "Support"/"Information"/"Franchise" columns entirely rather than filling them with placeholder links.

---

## Judgment calls to confirm with the client

1. **Nav & hero CTA copy** ("View Menu" / "Order on WhatsApp" instead of "Order Now"; trust-badge labels) — content decisions, not styling, need real copy.
2. **Promo banner** repurposed from "20% off" to a "Menu of the Day" spotlight — no discount system exists; confirm this substitution is acceptable.
3. **Testimonials & hero rating card** — no reviews/ratings data model exists yet; these can only be static manual content unless a reviews feature gets scoped as a real backend addition.
4. **Blog/Articles section** — explicitly out of scope per `backend/CLAUDE.md`; recommend dropping or repurposing as an Instagram feed strip, pending client input.
5. **Newsletter band** repurposed as a WhatsApp CTA strip — no email subscription system exists; this substitution matches how the business actually takes orders.
6. **Footer link columns** — trimmed from the reference's multi-location e-commerce set down to what a single home-kitchen business actually needs.
7. **Two color/font gaps** flagged inline: no defined "light section background" tint (Sections 5 & 7) and no defined star-rating color (Sections 2 & 5) — both given reasonable pink-tinted/gold defaults pending a pixel-exact brand pass (`design.md` itself notes the primary pink is a visual estimate, not pixel-measured).
