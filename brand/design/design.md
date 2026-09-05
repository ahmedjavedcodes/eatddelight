# Daughter's Delight (@eatddelight) — Design Guidelines

*Extracted from: https://www.instagram.com/eatddelight/ (profile grid, highlight covers, bio) on 2026-09-04*

## Overview
Daughter's Delight is a home-kitchen food business (Instagram: @eatddelight) selling daily specials and a full à la carte menu. The Instagram presence reads as warm, homemade, and feminine — bright pink/magenta branding over white, rounded friendly typography, and appetizing top-down food photography, closer to "cozy neighborhood kitchen" than a slick restaurant chain.

## Color Palette

| Role | Hex | Notes |
|---|---|---|
| Primary (brand pink) | ~#E91E8C | Visual estimate from the profile logo and menu graphics — a saturated hot pink/magenta. Appears consistently in the logo badge, menu headers, and wavy background shapes. **Not pixel-measured** — see note below. |
| Secondary | ~#FFFFFF | Clean white, used as the dominant background on menu graphics and negative space around the pink. |
| Accent/Text-on-pink | #FFFFFF | Headings like "MENU", "MENU OF THE DAY" are set in white on the pink shapes. |
| Body text | #1a1a1a (near-black) | Standard dark text for captions/labels, nothing unusual. |

**On accuracy:** these hex values are a visual estimate from viewing screenshots of the Instagram profile, not a pixel measurement — Instagram blocks the kind of bulk image download that would let `extract_palette.py` run against real post images without an expensive detour (see the skill's own guidance on this). For a pixel-exact palette, the next step is to upload 2-3 actual photos (product shots, packaging, or a saved screenshot of a menu graphic) and run them through `extract_palette.py` directly — that will nail the exact pink down to the hex value instead of an estimate.

## Typography
- Headings ("MENU", "MENU OF THE DAY", "SUBSCRIPTION MENU"): bold, rounded sans-serif, all-caps, high weight — reads playful/friendly rather than corporate. Can't identify the exact typeface from a screenshot; category is something like a rounded geometric sans (think Poppins/Baloo/Fredoka territory), not a font with sharp serifs or technical/monospace character.
- Body/labels: a plain, legible sans-serif (system-default weight), no strong personality — this is likely just Instagram's own UI font in the screenshots, not necessarily the brand's chosen body font, so treat it as unconfirmed.
- Pairing notes: bold rounded display type over a plain body sans is a common, safe pairing that matches the "homemade but organized" tone.

## Visual Patterns
- Shape language: soft, rounded — the pink brand color is applied in large wavy/curved blob shapes rather than straight-edged blocks or sharp banners. This curviness is a consistent, repeated motif across multiple post graphics.
- Spacing/density: the menu graphics are fairly information-dense (multiple menu items, prices, day labels on one graphic) but organized into clear white cards/sections so it doesn't read as cluttered.
- Imagery style: bright, appetizing, top-down or 3/4-angle food photography — the food itself is the hero, shot in natural-looking light, not moody/dark styling.
- Iconography/motifs: small food emoji used in highlight/story labels (🍱 for Mandi, 🌼 for reviews) — a light, casual touch rather than custom iconography.
- Logo: a circular badge, pink background, white monogram-style mark (stylized "D" combined with a spoon/fork silhouette) with "Daughter'sDelight" wordmark — reads as a hand-crafted, friendly logo rather than a minimalist tech-style mark.

## Tone
Warm, homemade, approachable, family-run, unfussy — expressed through the pink-and-white palette (feminine, appetizing, not corporate), the rounded shapes and type, and bio copy like "Homemade goodness, freshly prepared with care 💕".

## Design Tokens
```json
{
  "brand": "Daughter's Delight",
  "colors": {
    "primary": "#E91E8C",
    "secondary": "#FFFFFF",
    "background": "#FFFFFF",
    "text": "#1A1A1A",
    "accent": "#E91E8C"
  },
  "fonts": {
    "heading": "rounded geometric sans-serif (category estimate — e.g. Poppins/Baloo/Fredoka; not confirmed)",
    "body": "system sans-serif (unconfirmed — not visible outside Instagram's own UI in source screenshots)"
  },
  "radius": "lg",
  "spacing": "comfortable",
  "tone": ["warm", "homemade", "approachable", "family-run"]
}
```
