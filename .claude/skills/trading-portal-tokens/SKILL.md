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
| `--color-surprise-up` / `-down` | `#5CC8FF` cyan / `#A78BFA` violet (proposed) | News actual above / below forecast. **Never** win/loss colours. Always with ▲/▼ and the difference ("▲ +0.2"); the words "Better/Worse than forecast" come from the event type's `higher_is_better`. 9.4:1 and 6.5:1 on `surface-1` |
| `--color-live` / `--color-stale` | `#2FD27F` / `#8F99AD` (proposed) | Live dot; paused/stale |
| `--color-owner-0` … `-7` | `#2EC4B6` teal · `#8FA3FF` periwinkle · `#FF7AC6` pink · `#D4B483` sand · `#C9A7F5` lilac · `#6FD3F2` sky · `#C2D94A` chartreuse · `#D98CB3` mauve (proposed) | Calendar owners and "logged by" chips **only** (`OwnerChip`, `ownerBg(index)`). Each user has a fixed `colour_index` 0–7. All ≥ 7:1 on `surface-1`; none is a reserved or brand hue |
| `--chart-grid` / `--chart-axis` | `rgba(255,255,255,.05)` / `.16` | Chart gridlines (hairline, solid) and axis lines. Charts read every colour at runtime (`components/charts/theme.ts`) |
| `--chart-series-1` / `-2` | `#2F7BFF` / `#5CC8FF` | First and second chart series (at most 2–3 per chart). Pass CVD separation and contrast; lighter than the dataviz lightness band, so always paired with a legend or direct label |
| `--color-print-*` | paper `#FFFFFF`, ink `#111827`, muted `#4B5563`, rule `#D1D5DB`, win `#0F7A43`, loss `#C2273A`, breakeven `#4B5563`, accent-soft, owner-0…7 darkened (proposed) | **Save as PDF only.** Swapped in under `@media print` and `:root[data-print]` so printouts read on paper (≥ 4.5:1 on white). Never used on screen |

Reserved colours mean one thing and are used for nothing else. Colour is never the only signal: wins and losses carry +/− or an icon.

**Stale figures** (offline, or an answer the service worker served from its cache): wrap the card's content in `StaleFigures` (`pages/hub/StaleStamp.tsx`, built on `useStaleness` in `lib/offline.ts`). It puts a `--color-stale` dot and `Last updated HH:MM` (`.num`, UK time, `role="status"`) under the card title and fades every `.num` inside to 70% (`[&_.num]:opacity-70`; muted labels stay ≥ 4.5:1 on `surface-1`). Never grey the whole card, never hide the figures, and never use win/loss colours for staleness. Fresh data renders untouched.

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
| `--dur-flash` | 600ms | Price tick flash fading out (`.price-flash`), Live data in motion |
| `--dur-launch` | 600ms (proposed) | Launch loader minimum on a tool's first open each UK day (F14); `--dur-standard` after that. Read as `dur.launch()` |
| `--dur-intro` | 1000ms (proposed) | The portal intro after sign-in (`components/PortalIntro.tsx`): the logo mark draws in as a price line and candles, then dissolves into the Hub. Once per UK day per device, Full motion only. Read as `dur.intro()` |
| `--ease-in-enter` | `cubic-bezier(.16,1,.3,1)` | **Ease-out** when things enter |
| `--ease-out-leave` | `cubic-bezier(.7,0,.84,0)` | **Ease-in** when things leave |
| `--ease-spring` | `cubic-bezier(.34,1.4,.64,1)` | Toggles, dragged items |

Rules:

- Animate only `transform` and `opacity`.
- `prefers-reduced-motion` is honoured globally, and so is the per-user Full / Reduced / Off setting (`data-motion` on `<html>`, from `user.motion_pref`). Read `motionLevel()` from `src/lib/motion.ts` before animating; use the presets there (`pageVariants`, `panelVariants`, `spring`). `motion` is the only animation library.
- First-load stagger is 30–50ms apart, on first load only.
- Launch loaders run for at least about 600ms and exit as soon as the tool is ready.
- **Hero ambience** (Hub only): the hero sets `data-daypart` (dawn 05–08 · day 08–17 · dusk 17–20 · night 20–05, UK) and `data-session` (asia · london · newyork · closed) and `.hero-atmosphere` changes only its two gradient mixes, all `color-mix()` of `--color-accent`, `--color-violet`, `--color-data-2`, `--color-news` and a little `--color-impact-medium` warmth at dawn and dusk. No new hex. Only opacity transitions, and it stays ≤ 0.55 (0.3 when markets are closed) so text keeps ≥ 4.5:1. The launch islands' accent glow (`.launch-island::after`, opacity only) is the one place the accent is used as a glow.
- Live data: `.price-flash` (win/loss wash fading over `--dur-flash`, always with ▲/▼), `.odo-digit`/`.odo-strip` (odometer roll), `.flip-in` (a released actual; a fade in Reduced). The news countdown pulses with `.pulse` only in its last 15 minutes.
- No looping motion at the screen edge. `.pulse` (2s, opacity only) is for cards fed by live data, never the shell. `.skeleton` shimmers at 1.4s. Both are loader rhythms outside the 150/250/500 tokens on purpose.
- The in-app Full setting overrides the OS reduce-motion preference on purpose (a user choice); Reduced and the default follow the OS.
- `motionLevel()` resolves exactly like the CSS: `data-motion="full"` → full (even when the OS prefers reduced motion), `"reduced"` → reduced, `"off"` → off, no attribute (signed out) → the OS setting. `resolveMotion(pref)` does the same from a stored preference.
- **Page transitions** (`components/PageTransition.tsx`, View Transitions API with a `motion` fallback): the shell stays still, the content cross-fades with a 10px rise over `--dur-standard`. Going back (a POP navigation) sets `<html data-nav="back">` for the length of the transition and the rise reverses. Off never calls `startViewTransition`.
- **Shared elements**: `vtName(kind, id)` on both ends (strategy card title ↔ strategy page heading, trade row instrument ↔ trade detail heading, ticker card ↔ instrument view, news row ↔ event detail). Only one element per name on screen: trade rows are named only when clicked (plus the row you came back from).
- **First-load stagger**: `<Stagger screenKey="…" as="ul">` (`components/ui/Stagger.tsx`) fades and rises its direct children 40ms apart (`STAGGER_STEP`) the first time that screen is shown this session (`useFirstLoad(key)`, a module-level `Set`); revisits render at once. Reduced: fade only. Off: nothing. Used on the Hub, Journal grid, News Room, Markets and Calendar.
- **Overlays** leave as well as enter: `anim-drawer-in` / `anim-sheet-in` + `anim-panel-out` (Drawer; from the right on tablet and up, up as a sheet on the phone, or out of the tapped row via `--origin-dx/dy` when the Drawer gets an `origin`), `anim-dialog-in/out` (ConfirmDialog, fade-and-scale .96 → 1), `anim-palette-in/out` (Cmd+K), `anim-toast-in/out` (slide up 16px in, fade out). `--dur-standard` in, `--dur-quick` out; Reduced maps every one to a fade; Off adds no animation classes.
- **Checkbox** (`components/ui/Checkbox.tsx`): a native input under a box whose SVG tick draws in (`pathLength`) over `--dur-quick`; fades in Reduced. Use it instead of a bare `<input type="checkbox">`.
- **MorphIcon** (`components/ui/MorphIcon.tsx`): a copy/download icon that morphs into a tick when done, over `--dur-quick`. Use it on every copy and export action.
- **Backtest unlock** (`StrategyPage.tsx`): when coverage reaches six months or "Open early" succeeds, `LockIcon` opens with a rotate-and-settle over `--dur-emphasis`, the Backtest pill gets a one-off `.unlock-ring` (opacity only) and a toast says "Backtest unlocked: six months of winners". Once per strategy per device (`localStorage tp.unlocked.<id>`). Process, not profit.
- Looping decoration (`.pulse`, `.skeleton`, `.unlock-ring`) pauses while the tab is hidden (`<html data-hidden>` from `installVisibilityPause()`).
- Deliberate exceptions to "transform and opacity only": the sidebar's `transition-[width]` and the content's `transition-[padding]` when the sidebar collapses (a rare, user-initiated layout change), and the countdown ring's `stroke-dashoffset` (a paint property on one small SVG).

## Not allowed on working screens

- Frosted glass or blur. The Hub hero card is the only atmospheric surface.
- Purple or neon gradients and 3D objects.
- Faint low-contrast text.
- Green or red used decoratively.
- Overlapping multi-line "neon" charts. Use at most 2–3 series per chart.
