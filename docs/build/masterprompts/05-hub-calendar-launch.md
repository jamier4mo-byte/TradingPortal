# Prompt 5 of 5: Hub, team calendar, motion polish and launch readiness

Paste everything below the line into a fresh `claude` session in `~/Desktop/Trading Portal`.

---

You are building the Trading Portal, Jamie's multi-tool trading web app, in this repo. This is **Prompt 5 of 5: the Hub, the team calendar, motion and launch screens, offline mode, backups and production readiness**. Prompts 1–4 are done; read their reports. Work fully autonomously from start to finish.

## Operating rules (apply all the way through)

- **Don't stop to ask.** If something is undecided, use the Defaults below or the most conservative reasonable choice. Record it under "Assumptions" and carry on. Stop early only if continuing would break one of these rules.
- **Read first, in full:**
  - `CLAUDE.md`
  - `docs/planning/trading-portal-foundations.md` (Look and feel; Motion, loading and engagement in full; Devices in full; section 1 in full)
  - `docs/planning/trading-portal-review-and-build-kit.md` (F2, F5, F7, F14, F15, F18, top-10 action 8, the build kit table for FullCalendar and Litestream)
  - `.claude/skills/trading-portal-tokens/SKILL.md`
  - `docs/build/PROGRESS.md` and every `PHASE-*-REPORT.md`

  Jamie's answers to earlier open questions override the Defaults.
- **Resume-safe.** Keep a `## Prompt 5` checklist in `PROGRESS.md`, tick each step and commit. Continue from the first unticked item.
- **Plan, then execute.** Use parallel subagents, for example one for the Hub, one for the calendar, one for ops/backups and one for the security review. Use Context7 for FullCalendar 6 (React and rrule plugins), Motion, the View Transitions API, Litestream, Tigris (S3-compatible) and Fly.io.
- **Git.**
  - Start from a clean local `main` and create `build/05-hub-calendar-launch` (or resume on it). Make small commits.
  - **Never** push, deploy, create Fly apps, volumes or storage, or set secrets. You write the runbook; Jamie runs it.
  - Merge into local `main` with `--no-ff` only if the gate passes.
- **Data.** Never read or write `~/ReplayJournal/data`. Dev and test data live under `/tmp/tp-*`. The old app is reference only.
- **Secrets** never go in the repo. Don't open `.env` with Read. Tests mock every network call, including S3, using moto or a local fake.
- **Schema** changes only through Alembic. Permissions are server-side and tested.
- **Design.**
  - Use the tokens skill, with no hex outside `@theme`.
  - The Hub hero card is the **only** atmospheric surface.
  - Every screen has the five states and is designed for phone, tablet and desktop.
  - Follow the frontend-design skill.
- **Quality bar.**
  - `make lint` and `make test` pass. New logic has tests; new screens have Playwright tests at 375px and 1440px, with axe.
  - Run `/check-devices` and the `design-reviewer`, and fix blockers and majors.
  - The Hub's initial JS stays ≤ 200KB gzip.
- **Don't loop.** If the same failure survives two genuine fixes, log it under "Known issues".

## Defaults

- **Calendar:** FullCalendar standard (MIT) with the rrule plugin. Never Premium.
- **Backups:** Litestream streams SQLite to a Tigris bucket. The database is restored on boot if a replica exists. Screenshots go to Tigris through an `S3Storage`, chosen with `STORAGE_BACKEND=local|s3`.
- **Hosting:** one always-on `shared-cpu-1x` machine in `lhr` with a 1GB volume. The target is under $5 a month (F2, F7).
- **Launch loaders** (F14): minimum about 600ms, exit as soon as the tool is ready, about 250ms after the first visit that day. Inline SVG plus Motion; no Lottie.
- **Portal intro:** about 1 second, once per day per device, skipped under Reduced/Off motion.
- **Engaging touches reward process, never profit.** No confetti on winning trades.

## Steps

**0. Preflight.** Check the branch, `PROGRESS.md` and the baseline `make lint`, `make test` and `make smoke`. List every route and confirm each one has all five states; fix any gaps as you go.

**1. Team calendar** (1.4)
- **Tables:**
  - `tasks`: owner, title, start and end or all-day, RRULE, description, category (Backtesting, Review, Admin, Other)
  - `task_exceptions`: per-occurrence edits, moves and deletions
  - `task_completions`: done per occurrence
- **Endpoints:** expand occurrences in a date range server-side. Edit and move offer "this occurrence" or "the whole series". Members change only their own tasks.
- **Screen** at `/calendar`:
  - Week view by default, plus day and month.
  - "+ New task" button and tap-a-day to add.
  - Owner colour dots and filter chips.
  - Drag to move, with the lift, drop-target and settle micro-interaction.
  - Mark done optimistically, with an undo toast and rollback if the save fails.
  - High-impact news shown as faint markers.
  - Themed entirely from tokens.
  - **Phone:** a day or 3-day agenda list; long-press to drag; swipe a task to complete it, with a visible button for the same action.
- Tests: recurrence expansion across DST, this-occurrence vs series edits, permissions.

**2. The Hub** (section 1, top to bottom as in 1.6)
- **Greeting hero card** (1.1):
  - "Good morning/afternoon/evening, Jamie" by UK time. "Welcome back" after a gap of a day or more.
  - "Today is Friday 17th October" (ordinal date) with a live UK clock (`.num`).
  - A session status line ("London session opens in 1h 20m", "Markets closed – weekend").
  - **Time-of-day ambience:** the gradient shifts through dawn, day, dusk and night, tinted by the active session, with a calmer, dimmer weekend state. This is the only atmospheric card.
- **Today's news card** (1.2): the headline line, events filtered to the user's instruments, impact chips with labels, forecast vs previous, "No high-impact news today." Tap opens the News Room. On the phone, the headline plus the top 3 events.
- **Launch islands** (1.3):
  - ReplayJournal and News Room cards with logos, a subtitle and a live mini-stat: "Last session: 10 trades · Strategy X" and "Next event: USD CPI in 2h".
  - Lift and accent glow on hover, a press state on touch.
  - Click plays the launch loader as the real loading screen:
    - Replay Journal: a **rewind** (candles draw in right to left as a playhead sweeps back)
    - News Room: a **radar pulse** or ticker-tape sweep
  - On the phone, the islands are two side-by-side tiles.
- **Team calendar card:** week on desktop, a day or 3-day agenda on the phone.
- **Live market panel** (1.5): the Prompt 4 watchlist, search and credits meter. A swipeable row of ticker cards on the phone.
- **First-run checklist** (F15): add your Twelve Data key, create a strategy, import your first CSV, enable alerts, install to the home screen. Each item ticks itself off as it's done.
- **Process streak:** days with a session logged or a review done. Quiet, rewarding showing up rather than winning.
- **Personal bests:** best month in R, longest run of rule-following trades. One restrained celebration for a big milestone.
- **Week behind / Week ahead:** from Sunday evening, last week's recap sits beside the Week ahead view.
- **Big screens** show extra panels rather than stretched cards. Lazy-load everything below the fold.

**3. Motion pass across the whole app** (Motion section, F18)
- **Page transitions:** a cross-fade with an 8–12px rise while the shell stays still, using the View Transitions API with a fallback.
- **Shared-element transitions:** strategy card → strategy page, trade row → trade detail, ticker card → instrument view, calendar event → detail, news event → event detail. Going back reverses them.
- **Staggered first-load entrance:** 30–50ms apart, first load only.
- Pill indicators slide, charts morph, numbers count up, toggles spring, ticks draw in, and copy icons morph to a tick.
- Toasts slide up from the bottom corner. Drawers slide in from the right, or up as a sheet on the phone.
- The Cmd+K palette opens with a fade-and-scale.
- **Backtest unlock moment:** the lock opens, the tab lights up and a toast confirms it.
- **Portal intro** after login: the logo mark draws in as a price line or candlestick, then dissolves into the Hub.
- The Motion setting Full / Reduced / Off is honoured everywhere: Reduced turns movement into simple fades, and Off removes animation.
- Only transform and opacity are animated, and animation pauses off-screen or in hidden tabs.
- Record a performance trace of a chart morph and the Hub load with the Chrome DevTools MCP, if it's available.

**4. PWA and offline** (Devices → On the phone like an app)
- Extend `sw.js`: cache the app shell, the last Hub API responses, prices and today's events.
- When there's no signal, show the cached data with the OfflineBanner and dim stale figures with "last updated" times.
- A launch screen that matches the portal intro, the dark status bar, and safe areas for the notch, Dynamic Island and home bar.
- Images are sized per device, and long trade lists load as you scroll.
- E2e test: go offline after loading the Hub, reload, and the cached Hub still shows with offline marking.

**5. Backups, storage and data safety** (F2, F5)
- **`S3Storage`** (Tigris, S3-compatible, using boto3) behind the existing `Storage` interface, with tests against moto. Add `make migrate-screenshots` to copy local screenshots to S3, resumable and idempotent.
- **Litestream:**
  - Add the binary to the Docker image, pinned to a version.
  - Add `litestream.yml`, using env vars for bucket, endpoint and keys.
  - Entrypoint: `litestream restore -if-replica-exists`, then `alembic upgrade head`, then `litestream replicate -exec "uvicorn ..."`. With no replica configured, fall back to plain uvicorn.
- **`make restore-test`:** restore from a replica (local file replica in tests) into `/tmp`, run `PRAGMA integrity_check`, and compare row counts. Write `docs/ops/RESTORE-TEST.md`, a quarterly drill for Jamie.
- **Trash purge:** remove soft-deleted records and their screenshots after 30 days. It's a daily scheduler job, using the Prompt 4 scheduler and lease.
- **Admin "Export everything":** a zip containing a consistent DB snapshot (made with the SQLite backup API), all screenshots and a manifest. It streams and is admin-only.
- `fly.toml`: confirm always-on, volume mount, health check on `/api/health`, and `[env]` for non-secret settings.

**6. Security and quality review**
- Run the `security-guidance` and `code-review` plugins if they're installed; otherwise use a dedicated review subagent. Cover:
  - auth, sessions, CSRF, lockout, invites and resets
  - role checks on every write endpoint (generate a route × role test table automatically from the OpenAPI schema)
  - upload validation and path traversal
  - zip export contents
  - key vault handling
  - SSRF in feed fetchers
  - security headers (CSP without `unsafe-inline` scripts, HSTS, frame-ancestors none, Referrer-Policy)
  - rate limits
  - dependency audit (`pip-audit`, `npm audit --omit=dev`)
- Fix everything high or medium.
- Accessibility sweep: axe on every route, keyboard-only walkthrough of the main flows, 200% text zoom, charts with summaries and tables, and focus rings visible everywhere.

**7. Optional "Could" items: only after everything above passes, one commit each, and stop if time or usage runs short**
- Flashcard review on the phone (U14)
- A Konva screenshot annotator (arrows, boxes, text) on Entry/Exit shots
- Mates presence dots and an activity feed

**8. Deploy runbook** (write it; don't run it)

Write `docs/DEPLOY.md` for Jamie, step by step, with exact commands:
- `fly auth login`
- `fly apps create trading-portal-jamie` (or the name from his answers)
- `fly volumes create portal_data --size 1 --region lhr`
- `fly storage create` for Tigris; note which secrets it sets automatically
- `fly secrets set` for each secret, by name with placeholders: `TRADING_PORTAL_SECRET_KEY` (and how to generate it), `JBLANKED_API_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`, Litestream/bucket settings, `STORAGE_BACKEND=s3`
- add the `FLY_API_TOKEN` GitHub secret
- `git push`, which starts CI and then the deploy
- `fly ssh console -C "make create-admin"` or its equivalent
- smoke checks: `/api/health`, sign-in, install to the iPhone home screen, test notification
- the first restore test
- how to check the monthly cost stays under $5

**9. Gate 5: final regression** (all must pass)
- `make lint`, `make test` and `make smoke` are green, the bundle budget passes and `docker build .` succeeds locally if Docker is available (if not, say so).
- `/check-devices` across **every** screen at 360, 375, 430, 768, 1440 and 1920px is clean.
- A design-reviewer pass over the **whole** `frontend/src` has no blockers or majors.
- Axe passes on every route.
- The restore test passes. The offline e2e passes. Calendar recurrence tests pass.
- The security review has no open high or medium findings.

## Finish

Write `docs/build/PHASE-5-REPORT.md`, with the same sections as before, plus `docs/build/FINAL-REPORT.md`:
- a section-by-section checklist of the Foundations doc (1.1–4.3, Look and feel, Motion, Devices), every F1–F19 and every U-idea, each marked Done / Partial / Deferred with a one-line note
- deviations from the docs and why
- open questions
- Could items left
- a suggested v1.1 list

Update `README.md` and `CLAUDE.md` so they describe the finished app. Tick `PROGRESS.md`, commit, merge locally if the gate passed, and print a short summary that ends with: "Ready to deploy: follow docs/DEPLOY.md."
