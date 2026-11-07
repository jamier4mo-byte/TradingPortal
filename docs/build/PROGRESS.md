# Build progress

One checklist per masterprompt. Each item is ticked when it lands and is committed on the
prompt's branch. If a prompt stops part-way, the next run continues from the first unticked item.

## Prompt 1 — Foundations (branch `build/01-foundations`)

### 0. Preflight
- [x] Clean `main`; only `docs/build/masterprompts/` and `.claude/settings.local.json` untracked
- [x] Branch `build/01-foundations`; `.claude/settings.local.json` git-ignored; masterprompts committed
- [x] Baseline: `make setup` OK · `make test` 2 passed · `make lint` clean · `make smoke` 10/10
- [x] MCP: context7 and github connected; playwright, chrome-devtools, flyctl pending approval
- [x] `docs/build/PROGRESS.md` created

### 1. Backend structure
- [x] `app/models`, `app/schemas`, `app/api`, `app/services`, `app/core` laid out
- [x] pydantic-settings; `TRADING_PORTAL_SECRET_KEY`; `make dev-secrets`; production refuses to start without it
- [x] Mixins: timestamps, soft delete, owner
- [x] `audit_log` table
- [x] Test fixtures: temp data dir, migrations, factories

### 2. Users, sign-in and roles
- [x] Tables: users, sessions, invites, password_resets, passkeys (migration)
- [x] Endpoints: login, logout, me, accept invite, forgot/reset, change password
- [x] Passkey register and login
- [x] Admin: invites, list users, change role, deactivate/reactivate
- [x] `make create-admin`
- [x] `require_admin`, `require_owner_or_admin`, scope filter
- [x] Tests: role × action matrix, lockout, invites, deactivated, CSRF, sliding session

### 3. Per-user key vault
- [x] `user_api_keys` table, Fernet, set/delete/test endpoints, tests

### 4. Shared tag vocabulary
- [x] `tags` table, admin CRUD + merge, member proposals, `resolve_tag`, seed migration, tests

### 5. Front-end foundation
- [x] TanStack Query + typed `api` client (CSRF, 401 → login); protected routes; role-aware UI
- [x] Auth screens: login (password/passkey), accept invite, reset, locked-out
- [x] App shell per device: sidebar / rail / bottom tabs, top bar (Cmd+K, clock, session, bell, avatar), safe areas
- [x] Shared components + `/dev/components` gallery
- [x] 8 owner colour tokens in `@theme` + tokens skill table
- [x] Admin pages: Users, Tags
- [x] Settings: profile, password, passkeys, API keys, motion, breakeven threshold
- [x] Motion foundation: `motion`, route transitions, presets
- [x] PWA basics: icons script, manifest, head tags
- [x] Bundle budget `scripts/check-bundle.mjs` in `make lint` and CI; lazy routes

### 6. Dev experience
- [x] `make seed-dev`
- [x] e2e: sign-in helper, auth flows, new routes in `capture.mjs`
- [x] `CLAUDE.md` → Commands updated

### 7. Gate 1
- [x] Admin signs in; member accepts invite in a second context
- [x] Member gets 403 on admin's records; read-only banner shown
- [x] Deactivation signs out and blocks sign-in; lockout after 5 failures
- [x] `make lint`, `make test`, `make smoke` green; axe on every route
- [x] `/check-devices` clean at 360/375/430/768/1440/1920; nav per device
- [x] design-reviewer: no blockers or majors
- [x] Bundle budget passes
- [x] `docs/build/PHASE-1-REPORT.md` written; merged to local `main`

## Prompt 2 — Replay Journal loop (branch `build/02-journal-loop`)

### 0. Preflight
- [x] Clean `main`; branch `build/02-journal-loop`; `/Samples/` git-ignored (Jamie's real files, read only)
- [x] Baseline: `make test` 136 passed · `make lint` clean · `make smoke` 46 passed
- [x] Old importer summarised; sample CSV header and screenshot names noted

### 1. Data model
- [x] Migration `0004_journal`: instruments, strategies, trade_sessions, trades, trade_tags, screenshots
- [x] Models + mixins; coverage/unlock constants in one module
- [x] Instrument seed: FX majors, XAUUSD, BTCUSD, GER40, NAS100

### 2. CSV importer
- [x] Parser: 22 columns, BOM, quoting, dates, empty cells, tags; timezone → UTC; market date; session label
- [x] Preview → confirm → Session; Ideal (winners only) / Backtest (all); duplicates skipped and reported
- [x] Undo session (soft delete) and restore
- [x] Fixture CSV + tests: DST, duplicates, breakeven ±2, winners-only, undo, malformed rows

### 3. Screenshots and matcher
- [x] `Storage` interface + `LocalStorage`; upload API (magic bytes, size, path-safe keys, thumbnail); authenticated serving
- [x] Matcher: filename patterns → capture time → sequence; unit tests
- [x] Browser pipeline: paste / drop / picker → WebP full + thumbnail; bulk matcher grid; phone list

### 4. Annotate mode
- [x] Full-screen stepper, Cmd+V flow, J/K/Esc, template fields, rulebook, tags autocomplete, MAE/MFE, autosave
- [x] Session inbox on the strategy page with Finish annotating

### 5. Strategy screens
- [x] Overview grid + New strategy form; ViewScopeToggle; phone single column
- [x] Strategy page tabs; Ideal Trades tab (list, quick log, coverage tracker, trade detail gallery)
- [x] Strategy profile; Backtest tab (locked / open early, profile, list, manual entry, import)
- [x] Session recap card; pre-session brief; missed setups; Trash; `GET /api/journal/summary`

### 6. Gate 2
- [x] Real CSV: Ideal (winners only), Backtest (all), third import all duplicates, undo + restore
- [x] Screenshots match ≥ 90% automatically; rest fixable in the grid
- [x] Keyboard-only Annotate mode completes 8 trades (Playwright)
- [x] Coverage/unlock unit tests (gap month, year boundary, midnight UK, deleted, exactly 6)
- [x] Member 403 + read-only banner
- [x] `make lint`, `make test`, `make smoke` green (208 pytest, 76 Playwright); `/check-devices` clean at 360/375/430/768/1440/1920; design-reviewer: two passes, no blockers or majors left
- [x] `docs/build/PHASE-2-REPORT.md`; merged to local `main`

### 7. Follow-up: manual annotation flow (branch `build/02b-manual-annotation`)
- [x] Slots HTF / Entry / Outcome (+ extras); migration `0005`; `annotated_at` and the manual completed mark
- [x] Annotate mode: three slots, Mark completed (⌘⇧↵), inbox counts completed; matcher and lists updated
- [x] Mark completed warns about missing images or reasoning, never restricts (branch `build/02c-completion-warning`)
- [x] 211 pytest · 76 Playwright · lint clean; merged to local `main`

## Prompt 3 — Analytics and Export for AI (branch `build/03-analytics-export`)

### 0. Preflight
- [x] Clean `main`; branch `build/03-analytics-export`
- [x] Baseline: `make test` 211 passed · `make lint` clean (Hub 184.3 KB) · `make smoke` 76 passed
- [x] FX Replay metric definitions summarised (`docs/build/research/fxreplay-metrics.md`); old app's analytics/export read

### 1. Metrics engine
- [x] Metric registry (id, label, unit, formula, function); FX Replay set + the doc's own
- [x] Breakdowns (hour, weekday, session, entry model, instrument, direction) and daily P&L calendar
- [x] Reconcile line against the CSV's own totals
- [x] `POST /api/analytics/query` with source, scope, split_by_owner and all 2.4 filters
- [x] Hand-computed metric tests (all wins, all losses, breakeven-heavy, single trade); 5,000 trades < 300 ms (144 ms)

### 2–6. Views, chart system and layout
- [x] Shared lazy `Chart` wrapper (echarts/core), runtime theme from CSS tokens, motion, crosshair, text summary + data table, skeletons
- [x] Ideal Trades views
- [x] Backtest views (KPI strip, equity, drawdown, streaks, breakdowns, calendar, R distribution, rulebook, exit efficiency, Monte Carlo worker)
- [x] Compare view; split by owner (small multiples above 3 owners)
- [x] Layout per device; Source PillToggle; filters in the URL

### 7–9. Insights, cards, export
- [x] Auto-insights card (Analytics tab and session recap)
- [x] Strategy cards: real headline stats
- [x] Export for AI zip, Copy for AI, CSV export, print stylesheet; export tests

### 10. Gate 3
- [x] Reconcile ✓ on the real CSV; KPI table in the report
- [x] Metric tests pass on every fixture
- [x] Filters morph charts; URL round-trips
- [x] AI export unzips; README_prompt reads well
- [x] `make lint`, `make test`, `make smoke` green (260 pytest + 6 Node · 110 Playwright); bundle 185.1 KB
- [x] `/check-devices` clean at six widths (`docs/check-devices/2026-11-06-p3/`); design-reviewer: pass 1 four majors fixed, pass 2 none
- [x] `docs/build/PHASE-3-REPORT.md`; merged to local `main`

### 11. Follow-up: Jamie's answers (branch `build/03b-breakeven-10`)
- [x] Breakeven ±$10 in $ (default, migration `0006` moves the old ±$2 and re-labels outcomes); Monte Carlo defaults to 10R; exit efficiency keeps FX Replay's best price
- [x] 262 pytest + Node · lint clean · smoke 109/110 (the 1 is the intermittent Annotate e2e, see Known issues); merged to local `main`

### 12. Follow-up: Annotate autosave race (branch `build/03c-annotate-autosave`)
- [x] Saves once per pause, in order; Mark completed queues behind the last save; regression e2e (old code kept "B")
- [x] lint clean · 262 pytest + Node · smoke 112/112; merged to local `main`

## Prompt 4 — News Room, live prices and push alerts (branch `build/04-newsroom-prices-alerts`)

### 0. Preflight
- [x] Clean `main`; branch `build/04-newsroom-prices-alerts`
- [x] Baseline: `make test` 262 passed
- [x] Keys by count: `TRADING_PORTAL_SECRET_KEY` 1 · `DEV_TWELVE_DATA_KEY` 0 · `JBLANKED_API_KEY` 0 · VAPID 0 (writing the keys from chat into `.env` was refused by the permission check)
- [x] Research: JB-News/JBlanked (free tier now 1 request a day, `/calendar/today/` only; keys are 30+ characters) and Twelve Data (1 credit per symbol, `/api_usage` costs 1, UTC-midnight reset, per-minute window, no gold or indices on Basic)
- [x] Foundation: settings, migration `0007` (16 tables + instrument map + symbol aliases), DB leases and rate slots, network guard for tests, scheduler skeleton in the lifespan

### 1. News data model and ingestion
- [x] Event-type catalogue (30+ explanations), migration `0008`
- [x] Forex Factory fetcher (hourly, upsert, UK/US DST), JBlanked fetcher (slot + daily budget), merge
- [x] `make news-backfill` (resumable, records coverage); feed runs and "last updated"
- [x] Fixture tests: parsing, DST, upserts, merge, lease, failure path

### 2. Trade ↔ news link
- [x] Tagging service (window per user, coverage, "No news data"), re-run when coverage grows
- [x] Analytics News filter live (inside/outside, by event type) + "Around news" breakdown
- [x] Pre-session brief news slot

### 3. Prices backend
- [x] PriceProvider protocol, TwelveDataProvider, FakePriceProvider
- [x] Per-key minute limiter (queues), daily credits, shared cache, pins (8)
- [x] Endpoints: search, quotes, sparkline, usage, pin/unpin; vault "Check key" calls Twelve Data
- [x] Daily-limit paused state; price-reaction job (opt-in, capped, leftover credits)

### 4. Push and the service worker
- [x] push_subscriptions / alert_prefs / alert_deliveries services and endpoints; `make vapid`
- [x] `public/sw.js` (push, notificationclick); Settings → Alerts flow (iOS guidance, permission on press, test, chime)
- [x] Scheduler tests with a frozen clock

### 5. News Room screens
- [x] Header, countdown ring, calendar day/week, filters, phone list + bottom sheet
- [x] Trading-day timeline; event detail; week ahead; alerts settings
- [x] Market components: TickerCard, InstrumentSearch, WatchlistRow, CreditsMeter, instrument view
- [x] `GET /api/news/today`, `GET /api/news/next`

### 6. Gate 4
- [x] Gate checks (see report; the Chromium push check is partial, see Known issues)
- [x] `make lint`, `make test`, `make smoke` green (467 pytest + 6 Node · 144 Playwright); Hub 187.8 KB
- [x] `/check-devices` at six widths (two rounds); design-reviewer: two passes, majors fixed
- [x] `docs/build/PHASE-4-REPORT.md`; merged to local `main`

## Prompt 5 — Hub, team calendar, motion, offline, backups and launch (branch `build/05-hub-calendar-launch`)

### 0. Preflight
- [x] Clean `main`; branch `build/05-hub-calendar-launch`
- [x] Baseline: `make lint` clean (Hub 187.8 KB) · `make test` 467 pytest + 6 Node · smoke deferred to the gate (144 at Prompt 4)
- [x] Docs read in full; Context7 works this session; Docker is **not installed** on this Mac (noted for Gate 5)
- [ ] Every route has the five states (checked in step 6's accessibility sweep)

### 1. Team calendar (1.4)
- [x] Migration `0009`: `tasks`, `task_exceptions`, `task_completions`
- [x] Occurrence expansion server-side (rrule, DST-safe); this-occurrence vs series edits and moves; members change only their own
- [x] `/calendar`: week / day / month, + New task, tap a day, owner dots and filter chips, drag to move, optimistic done with undo, news markers, tokens only
- [x] Phone: day / 3-day agenda, long-press drag, swipe to complete plus a button
- [x] Hub `CalendarCard` (week on desktop, agenda on the phone)
- [x] Tests: recurrence across DST, this-occurrence vs series, permissions; Playwright at 375 and 1440 with axe

### 2. The Hub (section 1)
- [x] `GET /api/hub`: welcome-back gap, process streak, personal bests, first-run checklist, week behind
- [x] Hero: greeting by UK time, Welcome back, ordinal date, live clock, session status line, time-of-day ambience with session tint and the weekend state
- [x] Today's news card (headline, my instruments, impact chips, forecast vs previous, empty state; phone: headline + top 3)
- [x] Launch islands with logos, mini-stats, hover lift and glow, press state, launch loaders (rewind / radar) as the real loading screen; phone tiles side by side
- [x] Team calendar card, live market panel (watchlist, search, credits; swipeable ticker row on the phone)
- [x] First-run checklist (F15), process streak, personal bests with one restrained celebration, Week behind / Week ahead from Sunday evening
- [x] Big screens get extra panels; everything below the fold lazy-loads; Hub initial JS ≤ 200 KB gzip

### 3. Motion pass (F18)
- [x] Page transitions (View Transitions + fallback), shared-element transitions for strategy / trade / ticker / calendar event / news event, reversed on back
- [x] Staggered first-load entrance; pills slide, charts morph, numbers count up, toggles spring, ticks draw, copy icons morph
- [x] Toasts from the bottom corner, drawers from the right / sheet on the phone, Cmd+K fade-and-scale, backtest unlock moment
- [x] Portal intro after login (once a day per device, skipped under Reduced / Off)
- [x] Full / Reduced / Off honoured everywhere; only transform and opacity; paused off-screen and in hidden tabs
- [x] Performance trace of a chart morph and the Hub load (Chrome DevTools MCP, if available)

### 4. PWA and offline
- [x] `sw.js`: app shell, last Hub API answers, prices and today's events cached
- [x] Offline: cached data with the OfflineBanner, stale figures dimmed with "last updated"
- [x] Launch screen matching the intro, dark status bar, safe areas; images sized per device; long trade lists load as you scroll
- [x] e2e: load the Hub, go offline, reload, cached Hub shows with offline marking

### 5. Backups, storage and data safety (F2, F5)
- [x] `S3Storage` (boto3, Tigris) behind `Storage`, `STORAGE_BACKEND=local|s3`, moto tests; `make migrate-screenshots` (resumable, idempotent)
- [x] Litestream: pinned binary in the Docker image, `litestream.yml` from env vars, entrypoint restore → migrate → replicate, plain uvicorn without a replica
- [x] `make restore-test` + `docs/ops/RESTORE-TEST.md`
- [x] Trash purge after 30 days (daily scheduler job with the lease)
- [x] Admin "Export everything" (streamed zip: consistent DB snapshot, screenshots, manifest)
- [x] `fly.toml`: always on, volume, health check on `/api/health`, `[env]` for non-secret settings

### 6. Security and quality review
- [x] Review: auth, sessions, CSRF, lockout, invites, resets; route × role table from OpenAPI; uploads and path traversal; zip export; key vault; SSRF; headers (CSP, HSTS, frame-ancestors, Referrer-Policy); rate limits; `pip-audit`, `npm audit --omit=dev`
- [x] Every high and medium fixed
- [ ] Accessibility sweep: axe on every route, keyboard walkthrough, 200% zoom, chart summaries and tables, focus rings

### 7. Could items (only after everything above passes)
- [ ] Flashcard review (U14) · Konva annotator · presence and activity feed

### 8. Deploy runbook
- [x] `docs/DEPLOY.md`

### 9. Gate 5
- [ ] `make lint`, `make test`, `make smoke` green; bundle budget; `docker build .` (not available here: say so)
- [ ] `/check-devices` at 360/375/430/768/1440/1920 clean; design-reviewer: no blockers or majors; axe on every route
- [ ] Restore test, offline e2e and calendar recurrence tests pass; no open high or medium security findings
- [ ] `PHASE-5-REPORT.md`, `FINAL-REPORT.md`, `README.md`, `CLAUDE.md`; merged to local `main`
