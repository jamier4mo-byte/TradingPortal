# Prompt 4 of 5: News Room, live prices and push alerts

Paste everything below the line into a fresh `claude` session in `~/Desktop/Trading Portal`. For live checks, first add `JBLANKED_API_KEY` and `DEV_TWELVE_DATA_KEY` to `.env`. This is optional; without them the prompt builds against fakes.

---

You are building the Trading Portal, Jamie's multi-tool trading web app, in this repo. This is **Prompt 4 of 5: News Room, live market data and push alerts**. Prompts 1–3 are done; read their reports. Work fully autonomously from start to finish.

## Operating rules (apply all the way through)

- **Don't stop to ask.** If something is undecided, use the Defaults below or the most conservative reasonable choice. Record it under "Assumptions" and carry on. Stop early only if continuing would break one of these rules.
- **Read first, in full:**
  - `CLAUDE.md`
  - `docs/planning/trading-portal-foundations.md` (1.2, 1.5, section 3 in full, Motion → Live data in motion, Devices → On the phone like an app)
  - `docs/planning/trading-portal-review-and-build-kit.md` (F1, F4, F7, F13, F19, U7, and the Decisions table: per-user Twelve Data keys, no Apify, push in v1)
  - `.claude/skills/trading-portal-tokens/SKILL.md`
  - `docs/build/PROGRESS.md` and every `PHASE-*-REPORT.md`

  Jamie's answers to earlier open questions override the Defaults. Where Foundations 4.2 and 4.3 conflict with the Decisions (a shared key, no always-on machine), **the Decisions win**.
- **Resume-safe.** Keep a `## Prompt 4` checklist in `PROGRESS.md`, tick each step and commit. Continue from the first unticked item.
- **Plan, then execute.** Use parallel subagents, for example one for the news feeds, one for the price provider and one for Web Push and the service worker. Use Context7 and the official docs for Twelve Data, JB-News (https://github.com/jblanked/JB-News), pywebpush, the Push API and Notifications.
- **Git.**
  - Start from a clean local `main` and create `build/04-newsroom-prices-alerts` (or resume on it). Make small commits.
  - **Never** push, deploy or set Fly secrets.
  - Merge into local `main` with `--no-ff` only if the gate passes.
- **Data.** Never read or write `~/ReplayJournal/data`. Dev and test data live under `/tmp/tp-*`. The old app is reference only.
- **Secrets.**
  - Keys come from the environment (`.env` locally) or the per-user vault, and are never in code, logs or responses.
  - Don't open `.env` with the Read tool. Check whether a key is present with `grep -c '^NAME=.' .env`.
  - **Tests and CI never call Twelve Data, JBlanked or Forex Factory.** Use recorded fixtures and a `FakePriceProvider`.
- **Schema** changes only through Alembic. Permissions are server-side and tested.
- **Design.**
  - Use the tokens skill, with no hex outside `@theme`. The News Room's violet→purple identity appears **only** on its brand mark and hero moments.
  - Impact uses the reserved red, orange and yellow **with** High/Med/Low labels.
  - Every screen has the five states and is designed for phone, tablet and desktop.
- **Quality bar.**
  - `make lint` and `make test` pass. New logic has tests.
  - New screens have Playwright tests at 375px and 1440px, with axe.
  - Add an e2e test asserting the browser **never** calls Twelve Data directly.
  - Run `/check-devices` and the `design-reviewer`, and fix blockers and majors. The bundle budget still passes.
- **Don't loop.** If the same failure survives two genuine fixes, log it under "Known issues".

## Defaults

- **Schedule:** the Forex Factory weekly JSON at `https://nfs.faireconomy.media/ff_calendar_thisweek.json`, fetched at most hourly, server-side, cached and upserted.
  - **Never** scrape forexfactory.com pages.
  - Send a generic `User-Agent: TradingPortal/1.0`, with no personal email.
- **Actuals and history:** the JBlanked News API with one server-side key (`JBLANKED_API_KEY`).
  - Make at most **1 request every 5 minutes globally**, enforced with a DB-backed lease so it holds across processes.
  - Results are shared by all users.
  - Run a one-off, resumable history load (F4).
  - **No Apify, no paid backfill.**
- **Coverage of news history:** trades outside the stored history window get "No news data", and the UI says so.
- **Instrument mapping** (3.1 plus F19) lives in one editable table, seeded:
  - USD → XAUUSD, BTC/USD, EUR/USD, NAS100
  - EUR → EUR/USD, GER40; DE → GER40
  - GBP → GBP/USD; JPY → USD/JPY; AUD → AUD/USD; CAD → USD/CAD; CHF → USD/CHF; NZD → NZD/USD

  Users choose the instruments they follow. The default is FX majors, XAUUSD, BTC/USD, GER40 and NAS100.
- **News windows:** 15 minutes either side of high-impact events, adjustable per user.
- **Surprise colouring:** **don't** use the win/loss colours, because those are reserved.
  - Add two new tokens, `--color-surprise-up` and `--color-surprise-down` (for example cyan `data-2` and violet), to `@theme` and the skill.
  - Always pair them with ▲/▼ and the difference.
  - Each event type has a `higher_is_better` flag that decides the wording ("better/worse than forecast").
  - Flag the choice in the report.
- **Prices** (F1, F13): every user's requests use **their own** Twelve Data key from the vault.
  - A `PriceProvider` protocol (search, quote, time_series, usage) with a `TwelveDataProvider` and a `FakePriceProvider`. Use the fake in dev when no key is set.
  - Each key has a token bucket of 8 requests per minute, and requests queue rather than fail.
  - Each user has a daily credit counter of 800, resetting at Twelve Data's daily reset (UTC midnight unless their docs say otherwise).
  - A **shared cache** keyed by symbol: quote 15 minutes, sparkline 15 minutes, search 24 hours. Credits are charged to whoever's key fetched.
  - Pins are capped at 8 per user.
  - Refresh every 15 minutes, only while a Hub or price view is visible, and pause when the tab is hidden. Refresh less often on the phone.
  - Label prices "Delayed · updated HH:MM".
  - Symbol aliases in a table (XAUUSD → XAU/USD and so on). If an instrument isn't available on the user's plan (GER40 and NAS100 are unconfirmed), show "Not available on your Twelve Data plan". Never fake a price.
- **Price reactions** (3.3): computed once per release and stored, at 5, 15 and 60 minutes after it: range in pips/points and direction.
  - They run only with credits a user has **opted in** to share, through an "Allow background jobs to use my key" setting, default off.
  - Each day is capped (default 150 credits) and the job only uses credits that are left over.
  - Watchlist and search always come first.
- **Push alerts** (F7, settled for v1): Web Push with VAPID keys. `make vapid` writes `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` and `VAPID_SUBJECT=mailto:` (a placeholder for Jamie to set) into `.env`.
  - An in-app scheduler runs on the single always-on machine: an asyncio task started in FastAPI's lifespan, single-instance guarded by a DB lease, ticking every minute.
  - Default alert: 15 minutes before high-impact events in the user's currencies.
  - Delivered once per user, device and event, using a dedupe table. Subscriptions are pruned on 404/410.
  - It also refreshes the news feeds on schedule.
- **Fly config:** set `auto_stop_machines = "off"` and `min_machines_running = 1` in `fly.toml`, with a comment pointing to F7. This is only a file change; nothing is deployed.

## Steps

**0. Preflight.** Check the branch, `PROGRESS.md`, the baseline tests and which keys are present (by count only). Have subagents:
- read the JB-News README to get the endpoints, authentication and limits
- read Twelve Data's API docs to get the credit cost per endpoint, the rate limits, the reset time, `/api_usage`, and the exact symbol names for XAU/USD, GER40/DAX and NAS100

**1. News data model and ingestion**
- **Tables:**
  - `event_types`: canonical name, currency, `higher_is_better`, a plain-English explanation and why it matters. Write short explanations for at least the 30 most common high-impact events: NFP, CPI, Core CPI, FOMC rate decision, Fed speeches, GDP, PMIs, retail sales, ECB, BoE, ZEW, Ifo, unemployment and so on.
  - `events`: source ids from both feeds, type, time in UTC, impact, forecast, previous, actual, revised, last-fetched.
  - `news_history_coverage`: date ranges where real history exists.
  - `feed_runs`: status and error, so failures are logged and visible.
- **Fetchers:**
  - Forex Factory: hourly, upsert.
  - JBlanked: 5-minute lease, actuals.
  - `make news-backfill`: a resumable JBlanked history load that respects the limit and records coverage.
- If one feed fails, the other still drives the schedule. "Last updated" is exposed to the UI.
- Tests use recorded fixture JSON for both feeds: parsing, timezone handling (FF times to UTC across DST), upserts, merging the two sources, the lease, and a failure path.

**2. Trade ↔ news link** (3.6, F4)
- A tagging service marks each trade inside/outside a news window: mapped instrument × event currency, using the user's window size, storing the event references.
- Trades outside the history coverage get "No news data". The service re-runs when coverage grows.
- **Analytics:** make the News filter from Prompt 3 live (inside vs outside, by event type), plus an "Around news" breakdown.
- **Pre-session brief** (U7): fill the news slot with stored events for the next uncovered month.

**3. Prices backend**
- The provider, buckets, credits, cache and pins as in Defaults.
- Endpoints: search (autocomplete), quotes for pins, sparkline, usage meter, pin and unpin.
- The vault's "Test key" now calls the cheapest real endpoint (`/api_usage` if it's free).
- A "Live data paused – daily limit reached" state that serves the last known prices.
- Price-reaction job as in Defaults, with tests.

**4. Push and the service worker**
- `push_subscriptions` (per device), `alert_prefs` (minutes before, currencies, impacts, quiet hours, optional) and `alert_deliveries` (dedupe).
- A hand-written `public/sw.js`, registered once. It handles `push` and `notificationclick` (opening the event detail) and nothing else yet; offline caching comes in Prompt 5.
- Enabling flow in Settings → Alerts:
  - Detect iOS when it isn't installed and show "Add to Home Screen to get alerts" guidance (iOS 16.4+).
  - Ask for permission only after a button press.
  - A **Send test notification** button.
- An optional soft chime for news alerts, off by default.
- Scheduler tests use a frozen clock: due alerts are sent once, quiet hours are skipped, dead subscriptions are pruned and the lease stops duplicate schedulers.

**5. News Room screens** (section 3)
- **Header** with the News Room logo.
- **Next high-impact countdown** pinned at the top:
  - The ring depletes as time runs down.
  - In the last 15 minutes it turns orange, then red, with a gentle pulse that respects Motion settings.
  - When the figure is released, the actual flips in.
- **Calendar:**
  - Day and week views in UK time, today by default.
  - Each event shows time, currency, name, impact chip with label, and actual / forecast / previous, with surprise styling.
  - Filters: currency, impact and "my instruments only".
  - On the phone, a list grouped by time, with filters in a bottom sheet.
- **Trading-day timeline** (3.2):
  - Asia, London and New York session bands, with event markers.
  - Shaded news windows.
  - A moving "now" line, and the current session softly highlighted.
  - On the phone, it scrolls sideways with "now" centred.
- **Event detail** (3.3), with a shared-element transition from the list. It shows:
  - the explanation
  - the release history table (actual, forecast, previous, surprise)
  - a price-reaction table at 5, 15 and 60 minutes
  - a summary sentence, such as "US CPI: XAUUSD has averaged a 180-point range in the first 15 minutes over the last 12 releases."
  - honest empty states when there's no data yet
- **Week ahead** (3.4): key high-impact events by day, with affected instruments. It's the default view from Sunday 18:00 UK.
- **Alerts settings** screen.
- **Market components for the Hub** (built here, placed on the Hub in Prompt 5):
  - A `TickerCard`: instrument, price, change, % change, day high/low, sparkline, "Delayed · updated" label, a live dot that turns grey when paused, odometer digit roll and a brief green/red flash fading over about 600ms. The flash is the only decorative use of green/red, because it shows price direction; pair it with ▲/▼.
  - `InstrumentSearch` with autocomplete.
  - A `WatchlistRow` that swipes on the phone.
  - A `CreditsMeter`.
  - An **Instrument view** page.
- **Hub endpoints for Prompt 5:** `GET /api/news/today` (headline line, for example "3 high-impact events today – USD CPI at 13:30", plus events filtered to the user's instruments) and `GET /api/news/next`.

**6. Gate 4 checks** (all must pass)
- With fixtures, and live if the keys are in `.env`:
  - Today's events show in UK time.
  - The countdown is correct.
  - The JBlanked lease never allows two calls within 5 minutes (test).
- Trades are tagged inside/outside windows correctly, and "No news data" appears outside coverage (tests). The Analytics News filter works.
- Prices:
  - Credits are counted per user.
  - The cache prevents a repeat call within 15 minutes (test).
  - The 8/min bucket queues requests.
  - The browser never calls Twelve Data (e2e).
  - With `DEV_TWELVE_DATA_KEY`, one live quote works for EUR/USD, and XAU/USD, GER40 and NAS100 availability is recorded in the report.
- The scheduler sends a due test alert exactly once (test). The local "Send test notification" works in Chromium.
- `make lint`, `make test` and `make smoke` are green, and the bundle budget passes.
- `/check-devices` is clean for the News Room, event detail, week ahead, alerts settings and instrument view at all six widths. The design-reviewer has no blockers or majors.

## Finish

Write `docs/build/PHASE-4-REPORT.md`:
- What was built
- The gate checklist
- **Twelve Data coverage findings** (XAU/USD, GER40, NAS100) and the credit cost per endpoint
- JBlanked history coverage achieved
- Assumptions, including the surprise colours
- Numbered open questions
- Known issues
- Production secrets needed (`JBLANKED_API_KEY`, the VAPID trio, `TRADING_PORTAL_SECRET_KEY`)
- "Jamie's check (10 min)": add his Twelve Data key in Settings, pin instruments, open the News Room, enable alerts on his iPhone after deploy (marked "after deploy")

Tick `PROGRESS.md`, commit, merge locally if the gate passed, and print a short summary.
