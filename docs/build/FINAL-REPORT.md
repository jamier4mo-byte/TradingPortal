# Final report: Trading Portal v1

Five prompts, 5–6 Nov 2026, branches `build/01` … `build/05`, merged into local `main`. This report checks the finished app against the Foundations doc, the review kit's F1–F19 and the U-ideas, then lists deviations, open questions, the Could items left and a suggested v1.1. Phase detail lives in `PHASE-1-REPORT.md` … `PHASE-5-REPORT.md`.

Status words: **Done** = built and tested · **Partial** = built with a gap named in the note · **Deferred** = not built, with the reason.

## Foundations doc, section by section

### Look and feel

| Section | Status | Note |
|---|---|---|
| Principles (instrument, high resolution, calm density, colour means something, one system) | Done | One card pattern (`components/Card.tsx`), tokens in `@theme`, 1px borders, `.num` everywhere; the design-reviewer ran at every gate |
| Colour (base, one accent, reserved meanings, owner colours, text, dark first) | Done | Win/loss/breakeven, impact, surprise and owner hexes are **proposed** values awaiting Jamie; light mode not built (doc: later) |
| Typography (Inter + tabular figures, JetBrains Mono, scale, Archivo wordmarks only in logos) | Done | Fonts bundled, no CDN |
| Brand marks (four marks, head tags, clear space, no recolouring) | Done | F17 head tags fixed; `make icons` regenerates favicons, apple-touch-icon, startup images and the manifest from the T tile |
| Layout and components (shell, grid, card pattern, hero card, KPI strip, ticker cards, pills, chips, gauges, launch islands) | Done | Hero is the only atmospheric surface (time-of-day ambience) |
| Charts (thin lines, faint grid, crosshair, equity in R, bars, heatmap, ≤ 3 series, sparklines) | Done | ECharts behind one lazy `Chart` wrapper with runtime theme from tokens, summaries and data tables |
| What to avoid | Done | Checked by the design-reviewer each phase; the rewind loader's candles use accent/subtle, not win/loss |

### Motion, loading and engagement

| Section | Status | Note |
|---|---|---|
| Motion principles (purposeful, fast, one language, transform/opacity only, Full/Reduced/Off) | Done | Tokens 150/250/500 ms, two easings and a spring; `motionLevel()` matches the CSS (Full overrides the OS setting on purpose) |
| Fades and page transitions (shell still, cross-fade + rise, shared elements, stagger, pills, drawers) | Done | View Transitions API with a `motion` fallback; back reverses; shared elements for strategy, trade, ticker, calendar, news event |
| Loading screens and states (portal intro, launch loaders, skeletons, stepped progress, instant actions, empty states, stale data) | Done | Intro once a day per device; loaders ≥ 600 ms first open per day then 250 ms; CSV import stages; optimistic done with undo |
| Live data in motion (odometer, flash, sparklines, live dot, countdown, timeline now line, meters) | Done | Phase 4 |
| Charts that animate (draw in, morph, hover, heatmap fade) | Done | Phase 3 |
| Micro-interactions (buttons, toggles, ticks, cards, drag and drop, paste, copy → tick, toasts, Cmd+K) | Done | Phase 5 pass: drawn ticks, MorphIcon, toast slide, drawer exits, palette fade-and-scale, calendar drag lift/settle |
| Engaging touches (ambience, backtest unlock, session recap, week behind/ahead, streaks, personal bests, mates later, sound) | Partial | All built except **Mates presence and activity feed** (doc says "later"; a Could item). Sound = the optional alert chime |
| What to avoid / Build notes | Done | Motion is the only animation library; no Lottie; inline SVG loaders; Hub JS under 200 KB gzip |

### Devices and responsiveness

| Section | Status | Note |
|---|---|---|
| What each device is for; layout and breakpoints (five sizes, grids, big screens get extra panels) | Done | Tailwind breakpoints 600/1024/1440/1920; Analytics and the Hub use side columns from 1440 |
| Navigation by device (sidebar, collapsible, rail, bottom tabs + "+" + sheets) | Done | Phase 1 |
| Key screens on mobile (Hub, Journal, quick log, Analytics, News Room) | Done | Agenda calendar, swipeable tickers, bottom-sheet filters, cards instead of tables |
| Touch, mouse and keyboard (44 px, no hover-only, gestures with buttons, keyboard, native pickers) | Done | Swipe-to-complete and swipe-to-unpin both have buttons |
| High-resolution screens (SVG icons, DPR canvases, thumbnails first, per-device images) | Done | `srcset`/`sizes` on screenshots, lazy decoding |
| Accessibility (WCAG 2.2 AA, colour never alone, screen readers, 200 % text, motion) | Done | axe on every route at 375 and 1440 in the smoke suite; chart summaries and data tables; see Phase 5 sweep |
| On the phone like an app (installable PWA, push, safe areas, light offline) | Done | Service worker caches the shell, the last Hub answers, prices and today's events; offline e2e |
| Speed on mobile (load what's needed, fewer price refreshes, lists load as you scroll) | Done | Lazy routes and charts; 30-minute refresh on the phone; TradeList pages in 40 at a time |
| Testing and sign-off | Partial | Playwright at 375 and 1440 plus `/check-devices` at six widths every phase; **no real iPad, Android or Firefox pass** (Jamie's devices) |

### 1. Homepage: the Trading Hub

| Section | Status | Note |
|---|---|---|
| 1.1 Personal greeting header | Done | Greeting by UK hour, Welcome back after a day away, ordinal date, live clock, session status line |
| 1.2 Today's news overview | Done | Headline, my instruments, impact chips with labels, forecast vs previous, "No high-impact news today.", opens the News Room |
| 1.3 App launch islands | Done | Logos, mini-stats, lift and glow, press state, rewind / radar loaders as the real loading screen (F14) |
| 1.4 Team calendar | Done | Week/day/month, tasks with owners and categories, RRULE repeats, this-occurrence vs series, drag to move, done with undo, news markers; multi-user from day one (F11) |
| 1.5 Live market data | Done | Per-user Twelve Data keys (not one shared key: Jamie's decision), search, pins capped at 8, shared cache, credits meter, paused state |
| 1.6 Layout order | Done | Greeting → news → islands → calendar → market; mobile stacks, news collapsed to headline + 3 |

### 2. Replay Journal

| Section | Status | Note |
|---|---|---|
| 2.1 Strategy overview | Done | Cards with stage, counts, range, coverage bar, backtest stats, sparkline, owner |
| 2.2 Ideal Trades tab | Done | Catalogue of winners, quick log, coverage tracker, strategy profile at six months (or opened early) |
| 2.3 Backtest tab | Done | Unlock rule (F9), open early with a warning, profile at the top, CSV import (F3) and manual entry, rules followed |
| 2.4 Analytics tab | Done | Ideal / Backtest / Compare, every filter, FX Replay metric set + the doc's own (F16), Reconcile line, Monte Carlo, Save as PDF, CSV |
| 2.5 Export for AI (F8) | Done | Streamed zip + Copy for AI |

### 3. News Room

| Section | Status | Note |
|---|---|---|
| 3.1 Economic calendar | Done | Day/week, UK time, surprise colouring, countdown, filters, instrument map (F19 adds NAS100) |
| 3.2 Trading-day timeline | Done | Sessions, news windows (per-user size), now line |
| 3.3 Event detail | Done | Explanation, history, price reactions (opt-in background credits), summary sentence |
| 3.4 Week ahead | Done | From Sunday 18:00 UK; beside the Week behind recap on the Hub |
| 3.5 Alerts | Done | Web Push per user and currency, quiet hours, chime; **real-browser push not verified under automation** (Jamie's check) |
| 3.6 Link to the Replay Journal | Done | Inside/outside/No news data tagging, Analytics News filter, Around news breakdown |
| 3.7 Data and build notes | Partial | Forex Factory + JBlanked as designed; JBlanked's free tier is now **1 request a day** and never called live (no valid key yet), so history only grows forward (F4) |

### 4. Platform foundations

| Section | Status | Note |
|---|---|---|
| 4.1 Users, roles and sharing | Done | Invite-only, admin/member, Mine · Everyone · Others, owner on every record, server-side checks, route × role table generated from OpenAPI |
| 4.2 Tech stack and hosting | Done (revised) | Fresh FastAPI + React repo (Jamie's decision); **always-on** machine instead of scale-to-zero because v1 has push alerts (F2/F7); Litestream to Tigris; under $5/month |
| 4.3 One shared Twelve Data budget | Deferred (superseded) | Jamie chose per-user keys (F1/F13); the shared cache still means one fetch serves everyone |

## Review kit fixes F1–F19

| # | Status | Note |
|---|---|---|
| F1 Twelve Data rights, XAU, GER40 | Partial | Per-user keys behind one `PriceProvider`; live check: EUR/USD and XAU/USD work on Basic, GER40 and NAS100 are "Not available on your plan"; display-rights wording is Jamie's open question |
| F2 Stack and hosting under $5 | Done | One `shared-cpu-1x`, 1 GB volume, Tigris; ≈ $3.90/month estimate in `docs/DEPLOY.md` |
| F3 CSV import spec | Done | Column map from the real export, timezone per strategy, preview, duplicates per destination, undo |
| F4 News history for past backtests | Done (as decided) | Tag where free history exists, "No news data" elsewhere; no Apify |
| F5 Backup, restore, archive, delete | Done | Litestream, quarterly restore drill (`make restore-test`, `docs/ops/RESTORE-TEST.md`), 30-day Trash with purge job, admin Export everything |
| F6 Login, reset, removal | Done | Invite link, password + passkeys, lockout, admin reset links, Deactivate (never delete) |
| F7 Push in v1 on an always-on machine | Done | In-app scheduler with a DB lease; no external cron |
| F8 Export for AI | Done | Phase 3 |
| F9 One unlock rule | Done | 6+ trades across 6 consecutive months by market date |
| F10 Two screenshots per trade, WebP, badge | Done (revised) | Jamie's flow is three labelled slots (HTF / Entry / Outcome) + 3 extras; WebP ~1920 px + 400 px thumbs in the browser |
| F11 Multi-user calendar from release one | Done | `owner_id` on tasks |
| F12 Mine · Everyone · Others, split by owner | Done | Everywhere, plus Analytics split |
| F13 Pins capped at 8, 15-minute refresh, Delayed label | Done | 30 minutes on the phone; refresh pauses in hidden tabs |
| F14 Launch loaders ~600 ms min, exit when ready, 250 ms after | Done | Hub islands |
| F15 Five states per screen + first-run checklist | Done | Checklist ticks itself and hides when complete; five states checked in the Phase 5 sweep |
| F16 FX Replay metric set, Monte Carlo, Reconcile | Done | Phase 3 (breakeven ±$10, Jamie 6 Nov) |
| F17 Head tags | Done | Phase 1; startup images added in Phase 5 |
| F18 View Transitions + Motion only, inline SVG, 200 KB Hub | Done | Hub initial JS 192.8 KB gzip at v1 (ECharts, FullCalendar, the palette and the account menu are lazy) |
| F19 NAS100 in the instrument list and USD mapping | Done | Phase 2 and 4 |

## U-ideas

| # | Status | Note |
|---|---|---|
| U1 Session record + inbox | Done | Phase 2 |
| U3 Bulk screenshot matcher | Done | Real FX Replay files are hash-named, so they land by sequence and need a check in the grid |
| U4 Annotate mode | Done | Keyboard-only flow tested; autosave race fixed in 03c |
| U5 Structured reasoning + tag vocabulary | Done | Per-strategy template, shared ICT/SMC tags with synonyms, member proposals |
| U7 Pre-session brief | Done | Includes stored news for the month to replay |
| U9 Strategy rulebook checklist | Done | Rule cost in R in Analytics |
| U10 Excursion: R left on the table | Done (manual) | MAE/MFE typed in Annotate mode or FX Replay's ideal price; not computed from candles |
| U11 Auto-insights card | Done | Plain SQL/Python on request |
| U13 Missed / skipped setups | Done | Out of P&L, counted in adherence |
| U14 Flashcard review | Deferred | Could item; see below |
| (U2, U6, U8, U12 were folded into F3, F16, F8, F10) | Done | Through those fixes |

## Deviations from the docs, and why

1. **Always-on machine, not scale-to-zero** (4.2): push alerts and hourly feeds need a process running; Jamie approved it in the review kit (F7). Still under the $5 target.
2. **Per-user Twelve Data keys, not one shared key** (4.3/F1): Jamie's decision on 5 Nov; the shared server cache keeps the credit cost low anyway.
3. **Three labelled screenshot slots (HTF / Entry / Outcome)** instead of Entry/Exit (2.2, F10): Jamie's actual flow, 6 Nov; "Completed" is a manual mark.
4. **Breakeven is ±$10 in dollars** (F16): Jamie, 6 Nov (the kit assumed ±2).
5. **Calendar recurrence is expanded server-side** with dateutil rather than FullCalendar's rrule plugin, so the phone agenda, the Hub card and the API all agree; FullCalendar is pinned to 6.1.22 (v7 is incompatible with the v6 plugins).
6. **Litestream v0.5** (the kit assumed 0.3): single `replica:` and global snapshot settings; the entrypoint restores only onto an empty volume so a stale replica can never overwrite live data.
7. **Twelve Data `/api_usage` costs a credit**, so "Check key" spends 1.
8. **JBlanked free tier** is one `/calendar/today/` request a day (changed Sep–Oct 2026): actuals arrive once a day at 21:15 UK; no backfill without buying credits.
9. **Launch-loader candles are accent/subtle**, not green/red: the rule that reserved colours are never decorative wins over "candle direction".
10. **CSP allows inline styles** (`style-src 'unsafe-inline'`) because React, Motion and FullCalendar set `style=` attributes; scripts are strictly `'self'`.

## Open questions for Jamie

Collected from the five phase reports; unanswered ones only.

1. Accent buttons: keep dark ink, or darken the fill so white text passes AA?
2. Confirm the proposed hexes: win, loss, breakeven, impact orange/yellow, surprise cyan/violet, the eight owner colours.
3. Should a locked account say "locked" (reveals it exists) or "wrong email or password"?
4. Members seeing other members' email addresses: keep hidden?
5. FX Replay `tags` separator; whether `/screenshot` files can carry the trade id in their name.
6. Should a winner imported as Ideal also count in the Backtest ledger automatically?
7. Session windows Asia 00–08, London 08–16:30, New York 13:30–21:00 UK: keep?
8. "A breakeven ends a streak": right reading of FX Replay's Max consecutive?
9. JBlanked: paste the real 30+ character key; buy credits for history and same-hour actuals, or stay free?
10. Twelve Data terms: keep the shared price cache (one user's fetch shown to the others) or flip `SHARED_CACHE` to per user?
11. GER40 and NAS100 on Basic: leave "Not available", show labelled ETF proxies, or a paid plan?
12. Sparkline cache 15 or 60 minutes? Alerts for medium impact too? Week ahead with medium impact?
13. Should a trade held *through* high-impact news count as "inside" the window (entry time only today)?
14. Hub: the week-recap window (Sunday 18:00 → Monday 23:59 UK) and the streak definition (session logged, review note, trade logged or annotated) — happy with these?
15. Calendar: should members be able to mark other people's tasks done (admin only today)?

## Could items left

- **U14 Flashcard review** on the phone (entry shot only, call direction and model, tap to reveal): not started.
- **Konva screenshot annotator** (arrows, boxes, text) on Entry/Outcome shots: not started; `konva` + `react-konva` would be a lazy chunk.
- **Mates presence dots and activity feed**: not started; needs a `last_seen_at` poll and an activity table or a view over audit_log.

## Suggested v1.1

1. Jamie's device pass: iPhone (small and large), iPad, Android if a mate has one, Firefox on desktop; real-browser push and passkeys on the deployed host.
2. Buy a small JBlanked credit pack once, backfill the last two years of high-impact actuals, and re-run tagging (`make news-backfill`).
3. Flashcard review (U14) and the Konva annotator, in that order.
4. Light mode (tokens are ready; the brand marks need light versions).
5. A colour-blind-friendly palette option in Settings (Devices → Accessibility).
6. Mates presence and activity feed.
7. Real candles (Lightweight Charts, with attribution) on the instrument view and event reactions, if credits allow.
8. Sentry (free tier) for feed failures and front-end errors.
9. Per-user sparkline cache tuning and a weekly credit report.
10. Export-everything on a schedule to the bucket (the admin button exists; a weekly job is a few lines on the scheduler).
