# Phase 5 report: Hub, team calendar, motion, offline, backups and launch readiness

Branch `build/05-hub-calendar-launch`, 6–7 Nov 2026. Gate 5: see the checklist below. Companion documents: `SECURITY-REVIEW-5.md`, `offline-notes.md`, `five-states.md`, `../DEPLOY.md`, `../ops/RESTORE-TEST.md`, `FINAL-REPORT.md`.

## What was built

**Team calendar (1.4)** (`backend/app/{models,services,api,schemas}/calendar.py`, migration `0009`, `frontend/src/pages/calendar/*`, `lib/calendar.ts`, `components/calendar/CalendarCard.tsx`)
- Tables `tasks` (owner, title, description, category, all-day, start/end in UTC, zone, RRULE), `task_exceptions` (per-occurrence moves, edits and deletions keyed by the occurrence's original local date) and `task_completions`.
- Occurrences are expanded **server-side** with dateutil in the task's zone, then converted to UTC, so a weekly 09:00 UK task stays 09:00 across both clock changes; a series move shifts by wall-clock delta. Edits, moves and deletes take `mode=occurrence|series`. Members change only their own tasks; everyone reads everyone's. 62-day window cap.
- Repeat rules are hardened: daily is the finest frequency, no `BYHOUR/BYMINUTE/BYSECOND/BYSETPOS`, start within ten years, a strict character set (no `DTSTART`/`RDATE`/`EXDATE` smuggling), at most 200 occurrences per task per window; the policy applies on write, and a stored rule that no longer parses is skipped rather than failing the calendar.
- `/calendar`: FullCalendar 6.1.22 (standard, MIT; pinned because `@fullcalendar/react` resolves to v7) with week (default, Monday first, UK time, now indicator), day and month; our own 44 px toolbar; view and date in the URL; "+ New task" and tap-a-day; owner dot chips (remembered); drag to move with lift, drop highlight and settle; recurring drops ask "This occurrence / Whole series"; done is optimistic with an undo toast and rollback; high-impact news as faint 15-minute markers with an "H" glyph; other people's tasks read-only. Phone: a Day · 3 days agenda list with swipe-to-complete plus a Done button, long-press to drag in the grid.
- Hub `CalendarCard`: week strip on desktop, agenda on the phone; no FullCalendar in the Hub chunk.
- Seed: 11 relative-dated tasks, one weekly series with a moved and a completed occurrence.

**The Hub (section 1)** (`backend/app/{api,services,schemas}/hub.py`, `frontend/src/pages/Hub.tsx`, `pages/hub/*`, `components/launch/*`, `lib/hub.ts`, `lib/time.ts`)
- `GET /api/hub`: `welcome_back` (previous visit ≥ 24 h ago, tracked in `AppState`), the process streak (28 UK days: a session logged, a review note, a trade logged or annotated), personal bests (best month in R, longest run of rule-following trades, `is_new` within 7 days), the first-run checklist flags, and the week recap (Sunday 18:00 → Monday 23:59 UK).
- Hero: "Good morning/afternoon/evening, Jamie" (afternoon ends 17:00), "Welcome back" after a day away, "Today is Friday 7th November" with a live `.num` clock, a session status line ("London session · closes in 2h 05m", "Markets closed – weekend (opens Sunday 22:00)"), and the only atmospheric surface: `data-daypart` (dawn 05–08, day 08–17, dusk 17–20, night 20–05) and `data-session` drive the gradient through `color-mix()` of existing tokens; the weekend state is calmer and dimmer.
- Today's news card from `/api/news/today` and today's events for my instruments; impact chips with labels; forecast vs previous; "No high-impact news today."; phone shows the headline and top 3.
- Launch islands with the logos, subtitle and live mini-stat ("Last session: 10 trades · NAS100 silver bullet", "Next event: USD CPI in 2h"); lift, accent glow and a press state; **the launch loader is the real loading screen** (F14): the tool's chunk is imported on click, the overlay (rewind candles for the Journal, radar pulse for the News Room) holds `--dur-launch` 600 ms on the first open per UK day and 250 ms after, loops while loading, fades under Reduced and is skipped under Off. Candles use accent/subtle, never win/loss.
- Team calendar card, lazy market panel (watchlist rows, search, credits; a swipeable ticker row on the phone), first-run checklist (ticks draw in, hides when complete), "Showing up" streak, personal bests with one restrained celebration per best per device, Week behind beside Week ahead in the recap window. Side column from 1440 px; everything below the fold lazy-loads near the viewport.
- Fixed on the way: `lib/motion.ts` read durations assuming `ms`, but the production CSS minifies `600ms` to `.6s`, so built animations ran ~1000× too fast.

**Motion pass (F18)** (`lib/motion.ts`, `components/PageTransition.tsx`, `components/ui/{Stagger,Checkbox,MorphIcon,Toast,Drawer,ConfirmDialog,PillToggle,CountUp}.tsx`, `components/PortalIntro.tsx`, `lib/intro.ts`, `index.css`)
- `motionLevel()` now matches the CSS: Full overrides the OS reduce-motion setting on purpose; signed out follows the OS.
- Page transitions reverse on back (`data-nav="back"`), shared elements for strategy card → page, trade row → detail (named only on the clicked row), ticker → instrument, news event → detail; the calendar drawer grows out of the tapped row (Radix keeps `layoutId`/view-transition names unreliable there).
- First-load stagger (40 ms, first load only, `Stagger`), drawn Checkbox ticks, `MorphIcon` copy → tick, toasts slide up and fade out, drawers slide/sheet in and out, dialogs and the Cmd+K palette fade-and-scale (the palette and the account menu are lazy chunks), backtest unlock moment (lock opens, tab lights, toast; once per strategy per device), portal intro after sign-in once per UK day per device (skipped under Reduced/Off), animations pause in hidden tabs, TradeList renders 40 rows and loads more on scroll.
- Deliberate non-transform exceptions, documented in the tokens skill: sidebar width, content padding, the countdown ring's dash offset.
- DevTools traces on the built app: Hub load LCP 819 ms (TTFB 41 ms), CLS 0.00; chart morph INP 54 ms, CLS 0.00; no long-task or layout-shift insights.

**PWA and offline** (`public/sw.js`, `main.tsx`, `lib/offline.ts`, `lib/api.ts`, `pages/hub/StaleStamp.tsx`, `components/UpdateReady.tsx`, `scripts/make-icons.mjs`, `index.html`)
- The service worker caches the shell and hashed assets (cache-first), navigations (network-first → cached `index.html`, stored only when HTML outside `/api/`), and an allow-list of GET API routes (`/api/hub`, today's news, next event, quotes, pins, calendar occurrences, journal summary, `/api/auth/me`) network-first with a 4 s timeout, stamped `X-TP-Cached-At`, capped at 40 entries. Never: non-GET, other auth/admin/me routes, screenshots, anything else. The API cache is cleared on every sign-in/out POST, on `{type:"signed-out"}`, and on any 401/403.
- Offline: the `OfflineBanner`, stale figures at 70 % with a `--color-stale` dot and "Last updated HH:MM", writes fail fast with a friendly message, an "A new version is ready · Reload" bar on updates (the new worker waits for Reload).
- 18 iOS launch screens (bg token + T tile, 4.5–20 KB each) generated by `make icons` and linked between markers in `index.html`; `safe-x` gutters for the notch in landscape; manifest `id`/`categories`.
- Screenshots: thumb `srcset`/`sizes`, lazy and async decoding, intrinsic sizes; the full image only in the zoom viewer.

**Backups, storage and data safety (F2, F5)** (`services/{storage,backup,purge,export_all}.py`, `api/export.py`, `litestream.yml`, `backend/entrypoint.sh`, `Dockerfile`, `fly.toml`)
- `S3Storage` (boto3, Tigris: virtual-hosted addressing) behind `Storage`; `STORAGE_BACKEND=local|s3`; screenshot routes stream bytes when the store has no local path. `make migrate-screenshots` copies local → bucket, idempotent and resumable, including Trash items.
- Litestream **v0.5.14** pinned in a Docker build stage; `litestream.yml` from `BUCKET_NAME` / `AWS_ENDPOINT_URL_S3` / `AWS_REGION`; `entrypoint.sh`: `restore -if-replica-exists -if-db-not-exists` (never overwrites a database already on the volume) → `alembic upgrade head` → `replicate -exec uvicorn`; plain uvicorn without a bucket.
- `make restore-test`: real `litestream restore` when the binary and a replica are present, else a directory file replica; `PRAGMA integrity_check`, row counts live vs restored with a documented tolerance for volatile tables; `docs/ops/RESTORE-TEST.md` is the quarterly drill.
- Trash purge: soft-deleted records older than 30 days and their storage objects, once per UK day, as a scheduler job.
- Admin "Export everything": a streamed zip with a consistent SQLite snapshot (backup API; `sessions`, `invites` and `password_resets` rows removed and vacuumed), every screenshot, a README and a manifest with SHA-256s; admin-only, rate-limited, audited; button on Admin → Users.
- `fly.toml`: always on, volume at `/data`, health check on `/api/health`, `[env]` for the non-secret settings.

**Security review** (`core/headers.py`, `tests/test_route_roles.py`, `tests/test_security_headers.py`, `tests/test_ratelimits.py`, `SECURITY-REVIEW-5.md`)
- Strict CSP (`script-src 'self'`; inline styles allowed for React/motion/FullCalendar; `font-src data:` for the inlined fonts), HSTS in production, Referrer-Policy, nosniff, frame-ancestors none, Permissions-Policy, COOP; cache-control defaults per path.
- Request body caps (2 MB, larger for uploads and CSV), CSV 5 MB / 50 000 rows, per-user 10/min on exports and import preview, atomic reset-link claim, invite links bound to the configured origins, OpenAPI/ReDoc hidden in production, 422s under auth never echo the input.
- Route × role table generated from the routers: 9 public, 89 member, 12 admin; a new route must be classified or the test fails.
- `npm audit --omit=dev` and `pip-audit`: no known vulnerabilities; `make audit` and a CI step.

**Tests**: see the gate table for the final counts.

## Gate 5 checklist

| Check | Result | How verified |
|---|---|---|
| `make lint`, `make test`, `make smoke` green; bundle budget | Pass | lint clean (ruff, oxlint, tsc); **726 pytest + 6 Node**; **260 Playwright passed, 8 skipped** (keyboard and zoom checks run on the desktop project only) at 1440 and 375 px with axe; Hub initial JS **192.8 KB** of 200 KB, ECharts and FullCalendar lazy |
| `docker build .` | **Not run** | Docker is not installed on this Mac. Validated instead: `bash -n`/`sh -n` on the entrypoint, `litestream.yml` parsed after env expansion, `fly.toml` parsed, the Litestream tarball name and version from the docs; the first `fly deploy` is the real test |
| `/check-devices` at 360/375/430/768/1440/1920 clean | Partial | 186 screenshots captured in `docs/check-devices/2026-11-07-p5/` (not committed). Hub and calendar checked by hand at 375 and 1440: clean. The screen-by-screen review stopped about two-thirds through when the usage limit hit and reported no findings; the remaining screens were stopped to save usage. Automated layout checks (no horizontal scroll, 44 px targets, axe) pass on all 31 routes at 1440 and 375 |
| design-reviewer over `frontend/src`: no blockers or majors | Pass | One pass over the whole Prompt 5 diff: 0 blockers, 4 majors (Reload button and Completed pill at 4.16:1 on surface-2, done rows dimmed to a borderline contrast, the island `aria-label` hiding the live stat), all fixed, plus three minors (settle timing from the token, constant owner-chip labels, layout comment). Left as minors/nits: FullCalendar's "+N more" link and 31 px time slots on touch (the agenda and New task give a 44 px path), the Checkbox relies on its label for 44 px, the account menu's old animation class, error toasts in the loss tone (pre-existing convention), inactive streak dots under 3:1 |
| Axe on every route | Pass | `e2e/routes.spec.ts`: 31 routes (incl. invite, reset, 404) × 1440 and 375, zero violations; keyboard walkthrough with a focus-ring check on every Tab; 200 % zoom (360 px at DPR 2) on four screens; chart summaries and data tables on all 13 charts |
| Restore test passes | Pass | `restore-test --replica <dir>` against a seeded `/tmp/tp-restore-src`: `PRAGMA integrity_check` ok, every non-volatile table equal (users 3, strategies 5, trades 337, tasks 11…); `tests/test_backup.py` (10) covers the Litestream-binary path with a stand-in |
| Offline e2e passes | Pass | `e2e/offline.spec.ts`: Hub reload offline is served by the worker (`fromServiceWorker`), offline banner and "Last updated" stamps shown, private routes never cached, cold offline load shows the offline state |
| Calendar recurrence tests pass | Pass | `tests/test_calendar.py` (36): both DST changes, all-day across DST, COUNT/UNTIL, this-occurrence vs series, moves, deletions, completions, permissions, rule hardening |
| Security review: no open high or medium | Pass | `SECURITY-REVIEW-5.md`: no highs found; every medium fixed; two lows documented as accepted |

## Assumptions

1. **Calendar**: `occurrences` `to` is inclusive (as the News Room); `occurrence_date` is the original local date and follows a moved occurrence; `UNTIL` is read as local wall time; completing someone else's task is owner-or-admin; a series PATCH with `occurrence_date` is "this occurrence was dragged" and shifts the series by that wall-clock delta; all-day tasks snap to UK midnight; resizing by drag is off; `@fullcalendar/rrule` and `list` aren't used.
2. **Hub**: session hours Asia 00:00–08:00, London 08:00–16:30, New York 13:30–21:00 UK, weekend Friday 21:00 → Sunday 22:00; dayparts dawn 05–08, day 08–17, dusk 17–20, night 20–05; welcome back after ≥ 24 h; streak day = session created, improve note, trade logged, trade annotated (missed setups don't count); best month by Σ R of backtest trades per UK month; rule run needs ≥ 3 trades; week recap window Sunday 18:00 → Monday 23:59 UK; launch loader `--dur-launch` 600 ms (proposed token); intro `--dur-intro` 1000 ms (proposed).
3. **Motion**: Full overrides the OS reduce-motion setting (Phase 1 assumption, now in the JS too); trade rows carry a shared-element name only on click; the sidebar width and content padding transitions are kept as user-initiated layout changes.
4. **Offline**: the allow-listed routes are cached even though the API answers `no-store`/`private` for some of them: that is the point of the offline mode on a single-user device, and the cache is wiped on every sign-in/out and 401/403; `/api/auth/me` is cached so the shell can mount offline; stale figures fade to 70 % (60 % drops muted labels below AA).
5. **Backups**: Litestream 0.5 (single replica, global snapshot settings), `force-path-style: false` for Tigris, restore only onto an empty volume, 72 h retention, hourly snapshots, 20 s health-check grace; purge order screenshots → trade tags → trades → sessions → strategies, a purged session unlinks (never deletes) a restored trade; volatile tables (`sessions`, `leases`, `app_state`, `audit_log`, `price_cache`, `feed_runs`, `alert_deliveries`) are reported, not compared, in the restore test; `migrate-screenshots` and the export include Trash items so a restore still finds its files.
6. **Security**: `style-src 'unsafe-inline'` and `font-src data:` accepted; the 423 lockout disclosure kept (Phase 1); `Fly-Client-IP` trusted (behind Fly); in-memory limiters are fine for one process; password hashes and the encrypted vault stay in the admin export (unreadable without the secret), `push_subscriptions` keys too.
7. The Hub's rewind-loader candles use the accent and subtle tokens; green/red are never decorative, even as "candle direction".

## Open questions for Jamie

1. Keep the Hub session hours and the week-recap window above?
2. Should members be able to mark other people's calendar tasks done (admin only today)?
3. Repeat rules are capped at daily; do you ever need twice-a-day tasks?
4. The portal intro plays once a day per device after sign-in; keep it, or make it sign-in-only on the first visit ever?
5. Litestream retention is 72 hours of point-in-time history plus hourly snapshots; enough, or keep a week?
6. The Trash purge is 30 days (F5); keep?
7. Confirm the two proposed motion tokens (`--dur-launch` 600 ms, `--dur-intro` 1000 ms).
8. Should the admin export leave the encrypted API keys out entirely (they can't be decrypted without `TRADING_PORTAL_SECRET_KEY`, but a restore needs them)?

## Known issues

- `docker build` never ran locally (no Docker); the Litestream download isn't pinned by hash.
- Real-browser push, passkeys on the deployed host and the iPhone/iPad install are Jamie's checks after the first deploy (as in Phase 4).
- The calendar e2e saw two one-off failures during concurrent agent work (an axe check and the phone undo test) that passed on every rerun; `test_role_matrix[admin-GET /api/admin/export]` once hit a temp-dir cleanup race, since made `rmtree(ignore_errors=True)`.
- Hub ambience hue snaps at the daypart boundaries (08:00, 17:00, 20:00) rather than cross-fading two layers; the 1 s hero clock keeps ticking in hidden tabs (cheap).
- The `components/ui/index.ts` barrel is not tree-shaken into the Hub chunk, so unused shared components (Drawer, RingGauge, StatTile, Field…) ride along; Checkbox, MorphIcon and CountUp are deliberately kept out of the barrel.
- The Could items (U14 flashcards, Konva annotator, mates presence) were not started; see `FINAL-REPORT.md`.
- Dev seed gives Jamie a 1-day streak and a "new" rule-run best, so the celebration toast fires once per device in development.

## Production secrets needed

| Secret | Set by | Used for |
|---|---|---|
| `TRADING_PORTAL_SECRET_KEY` | Jamie | Vault key derivation; required in production |
| `JBLANKED_API_KEY` | Jamie | News actuals |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` | `make vapid` + Jamie | Web Push |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ENDPOINT_URL_S3`, `BUCKET_NAME` (`AWS_REGION` sometimes) | `fly storage create` | Screenshots (`S3Storage`) and the Litestream replica |
| `FLY_API_TOKEN` (GitHub) | Jamie | Deploys from CI |

Non-secret settings are in `fly.toml` `[env]`. Nothing was deployed and no secrets were set: `docs/DEPLOY.md` is the runbook.

## Jamie's check (15 min)

1. `make dev`, sign in: the portal intro plays once, then the Hub greets you with today's date, the live clock and the session line; the hero's colour follows the time of day.
2. Click **Replay Journal**: the rewind loader plays (~600 ms the first time today, shorter after) and lands on the journal. Back to the Hub: the News Room island shows the next event.
3. **Calendar**: drag the seeded "Backtest session" to another day → choose "This occurrence"; mark one done and press Undo in the toast; hide Sam with his owner chip; on a 375 px window the agenda lists today and the next two days (swipe a row right to complete it, or press Done).
4. Hub: tick off the **Getting set up** items (add your Twelve Data key, import a CSV, enable alerts); the card hides when all five are done. The **Showing up** streak counts the day.
5. Settings → Motion → **Reduced**: route changes fade, no stagger, no intro; **Off**: nothing animates. Back to Full.
6. Offline: load the Hub, turn Wi-Fi off, reload: the Hub still shows with the offline banner and "Last updated" stamps; Wi-Fi on, reload, banner gone.
7. Admin → Users → **Export everything**: unzip, open `db/portal.db` with any SQLite viewer, check `manifest.json`.
8. `make restore-test` (prints `PRAGMA integrity_check: ok` and the counts table; the Litestream path says it wasn't exercised until you're on Fly).
9. `make lint`, `make test`, `make smoke`, `make audit` are green.
10. Then follow `docs/DEPLOY.md`.
