---
name: trading-portal-tokens
description: The Trading Portal's design tokens — colour, type, spacing, radius, motion, breakpoints — and the rules for using them. Use before writing or reviewing any front-end style, colour, font, spacing, radius, shadow or animation value.
---

# Trading Portal design tokens

**Code source of truth:** the `@theme` block in `frontend/src/index.css` (Tailwind 4: every token is also a utility, e.g. `bg-surface-1`, `text-muted`, `rounded-card`, `duration-(--dur-quick)`).
**Direction source of truth:** `docs/planning/trading-portal-foundations.md` → *Look and feel*, *Motion, loading and engagement*, *Devices and responsiveness*.

Never hard-code a hex value, duration or easing outside `@theme`. Need a new value? Add a token there and to this table in the same change.

Values marked **proposed** weren't given in the Foundations doc; they're starting points for Jamie to confirm. Don't treat them as settled, and mention it if your change leans on one.

## Colour

| Token | Value | Use |
|---|---|---|
| `--color-bg` | `#0B0F1A` | Page. Deep navy near-black. Dark is the default and main target |
| `--color-surface-1` | `#121829` | Cards |
| `--color-surface-2` | `#182036` | Inner panels, inputs, hovers |
| `--color-border` / `-strong` | `rgba(255,255,255,.08)` / `.14` | Crisp 1px borders instead of heavy shadows |
| `--color-border-input` | `rgba(255,255,255,.35)` | Form-control boundary (`.input`): ≥ 3:1 for WCAG 1.4.11. Not for cards |
| `--color-text` | `#EEF1F8` | Primary text |
| `--color-muted` | `#AAB3C7` | Secondary text. Must stay clearly readable (≥ 4.5:1 on surface-1) |
| `--color-subtle` | `#7F8AA3` | Icons and decoration only, **never text** |
| `--color-accent` | `#2F7BFF` | The one brand accent: active states, primary buttons, selected toggles, focus rings |
| `--color-accent-hover` / `-soft` | `#4B8DFF` / `rgba(47,123,255,.14)` | Hover; selected-row fill |
| `--color-on-accent` | `#0B0F1A` | Text on accent fills (4.9:1). White on `#2F7BFF` is only 3.9:1 and fails WCAG AA for normal text. **Open question for Jamie:** keep dark ink, or darken the button fill so white passes |
| `--color-violet` | `#8B5CF6` | Brand gradient end. **Gradient `#2F7BFF → #8B5CF6` is for brand marks and hero moments only** (`.brand-gradient`; the Hub hero `.hero-atmosphere`; and `.brand-hairline`, a 2px rule under the logo on the auth screens only) |
| `--color-news` | `#C45BFF` | News Room's own colour: violet `#8B5CF6` → purple `#C45BFF` |
| `--color-data-2` | `#5CC8FF` | Second data series; never reads as the brand |
| `--color-win` | `#2FD27F` (proposed) | Win / profit / positive R. **Reserved** |
| `--color-loss` | `#FF5A66` (proposed) | Loss. **Reserved** |
| `--color-breakeven` | `#8F99AD` (proposed) | Breakeven (≈0, out to ±$10 by default). **Reserved** |
| `--color-impact-high / -medium / -low` | `#FF5A66` / `#FF9F43` / `#F5D547` (proposed) | News impact red/orange/yellow. **Reserved**, always with a High/Med/Low label |
| `--color-live` / `--color-stale` | `#2FD27F` / `#8F99AD` (proposed) | Live dot; paused/stale |
| `--color-owner-0` … `-7` | `#2EC4B6` teal · `#8FA3FF` periwinkle · `#FF7AC6` pink · `#D4B483` sand · `#C9A7F5` lilac · `#6FD3F2` sky · `#C2D94A` chartreuse · `#D98CB3` mauve (proposed) | Calendar owners and "logged by" chips **only** (`OwnerChip`, `ownerBg(index)`). Each user has a fixed `colour_index` 0–7. All ≥ 7:1 on `surface-1`; none is a reserved or brand hue |
| `--chart-grid` / `--chart-axis` | `rgba(255,255,255,.05)` / `.16` | Chart gridlines (hairline, solid) and axis lines. Charts read every colour at runtime (`components/charts/theme.ts`) |
| `--chart-series-1` / `-2` | `#2F7BFF` / `#5CC8FF` | First and second chart series (at most 2–3 per chart). Pass CVD separation and contrast; lighter than the dataviz lightness band, so always paired with a legend or direct label |
| `--color-print-*` | paper `#FFFFFF`, ink `#111827`, muted `#4B5563`, rule `#D1D5DB`, win `#0F7A43`, loss `#C2273A`, breakeven `#4B5563`, accent-soft, owner-0…7 darkened (proposed) | **Save as PDF only.** Swapped in under `@media print` and `:root[data-print]` so printouts read on paper (≥ 4.5:1 on white). Never used on screen |

Reserved colours mean one thing and are used for nothing else. Colour is never the only signal: wins and losses carry +/− or an icon.

## Type

| Token | Value |
|---|---|
| `--font-sans` | Inter Variable (`@fontsource-variable/inter`, bundled, no CDN) |
| `--font-mono` | JetBrains Mono, for symbols, timestamps and raw trade data |
| Numbers | Add `.num` (tabular-nums, slashed zero) to **every** price, P&L, R, %, count and clock |
| Scale | `text-label` 12/16 · `text-body` 14/20 · `text-title` 16/24 · `text-heading` 22/28 · `text-hero` 40/44 |
| Wordmarks | Archivo Black italic 900, used **only** inside the logo PNGs in `frontend/public/brand/`. Never for interface text. Never recolour, stretch, glow or shadow a logo |

Labels are small and sentence case. Card titles are medium weight. Hero numbers are large.

## Shape, spacing, layout

| Token | Value |
|---|---|
| `--radius-card` | 16px (cards) |
| `--radius-panel` | 10px (inner panels, inputs, buttons) |
| `--radius-pill` | 999px (pill toggles, chips) |
| `--spacing` | 4px grid |
| Gutters | `--gutter-phone` 16px · `--gutter-tablet` 24px · `--gutter-desktop` 32px |
| `--tap` | 44px minimum tap target (`min-h-11`, `size-11`) |
| Breakpoints | phone < 600 · `tablet:` 600 · `laptop:` 1024 · `desktop:` 1440 · `large:` 1920 |
| Grid | 4 columns on phone, 8 on tablet, 12 on laptop and up |
| Navigation | Phone: bottom tab bar. Tablet: icon rail. Laptop and up: full sidebar plus top bar |

Card pattern (`components/Card.tsx`): title and optional subtitle top-left, controls top-right, content below. Every card in every tool follows it. On big screens, show extra panels rather than stretching cards.

## Motion

| Token | Value | Use |
|---|---|---|
| `--dur-quick` | 150ms | Hovers, presses |
| `--dur-standard` | 250ms | Panels, tabs, fades |
| `--dur-emphasis` | 500ms (range 400–600) | Charts drawing in, unlocks |
| `--ease-in-enter` | `cubic-bezier(.16,1,.3,1)` | **Ease-out** when things enter |
| `--ease-out-leave` | `cubic-bezier(.7,0,.84,0)` | **Ease-in** when things leave |
| `--ease-spring` | `cubic-bezier(.34,1.4,.64,1)` | Toggles, dragged items |

Rules:

- Animate only `transform` and `opacity`.
- `prefers-reduced-motion` is honoured globally, and so is the per-user Full / Reduced / Off setting (`data-motion` on `<html>`, from `user.motion_pref`). Read `motionLevel()` from `src/lib/motion.ts` before animating; use the presets there (`pageVariants`, `panelVariants`, `spring`). `motion` is the only animation library.
- First-load stagger is 30–50ms apart, on first load only.
- Launch loaders run for at least about 600ms and exit as soon as the tool is ready.
- No looping motion at the screen edge. `.pulse` (2s, opacity only) is for cards fed by live data, never the shell. `.skeleton` shimmers at 1.4s. Both are loader rhythms outside the 150/250/500 tokens on purpose.
- The in-app Full setting overrides the OS reduce-motion preference on purpose (a user choice); Reduced and the default follow the OS.

## Not allowed on working screens

- Frosted glass or blur. The Hub hero card is the only atmospheric surface.
- Purple or neon gradients and 3D objects.
- Faint low-contrast text.
- Green or red used decoratively.
- Overlapping multi-line "neon" charts. Use at most 2–3 series per chart.
