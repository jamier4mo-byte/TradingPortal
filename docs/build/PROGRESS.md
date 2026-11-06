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
