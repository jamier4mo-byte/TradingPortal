# Phase 4 report: News Room, live prices and push alerts

Branch `build/04-newsroom-prices-alerts`, 6 Nov 2026. Gate 4: see the checklist below.

## What was built

**Foundation**
- Settings (from the environment / `.env`):
  - `TRADING_PORTAL_FEEDS` (`live`/`off`)
  - `TRADING_PORTAL_PRICE_PROVIDER` (`auto`/`twelve_data`/`fake`)
  - `TRADING_PORTAL_SCHEDULER`
  - the JBlanked interval and daily budget
  - and the unprefixed `JBLANKED_API_KEY`, `DEV_TWELVE_DATA_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` and `VAPID_SUBJECT`. Blank values count as missing.
- Migration `0007`: 16 tables, plus the editable instrument map (3.1 + F19) and the symbol aliases. Migration `0008`: 52 event types with plain-English explanations.
- `services/leases.py`: DB leases and rate slots shared by every process. The scheduler holds `scheduler`; JBlanked claims a `jblanked` slot, one request per 5 minutes globally.
- `services/http.py`: every outbound call goes through one client with `User-Agent: TradingPortal/1.0`. Under tests it **refuses all real network calls**, so tests can only use recorded fixtures and mock transports.
- `services/scheduler.py`: an asyncio task started in FastAPI's lifespan, ticking every minute. It is single-instance through the lease, and runs these jobs: news feeds, re-tagging when coverage grows, push alerts and price reactions. One failing job never stops the others.
- `fly.toml`: `auto_stop_machines = "off"`, `min_machines_running = 1`, with an F7 comment. This is a file change only; nothing was deployed.

**News** (`services/news/`, `api/news.py`)
- **Forex Factory:** the weekly JSON, fetched at most hourly (15 minutes after a failure), and upserted.
  - Times carry their US Eastern offset and are converted to UTC. The fixtures cover the late-October gap week, when NFP is 12:30 UK, and the week of the 1 November US clock change.
  - `ff_key` is a hash of currency + title + UK date, so a time change doesn't duplicate a row.
  - Rows the feed drops are removed unless they hold an actual, a JBlanked match or reactions.
- **JBlanked:**
  - Requests are spaced by the 5-minute slot and limited by a daily budget (default 1, see Assumptions).
  - Its zone-less MT5 server times are read as Europe/Athens (EET/EEST).
  - Rows merge with Forex Factory (same currency + event type + UK date, within 90 minutes), and JBlanked fills the actuals.
- If one feed fails, the other still drives the schedule. Every attempt is a `feed_runs` row, and `/api/news/status` exposes the last update.
- **`make news-backfill`:** a resumable month-by-month JBlanked range load. It waits for the slot, keeps a cursor in `app_state`, records coverage, and stops cleanly when the key is missing or invalid or credits run out.
- **Trade ↔ news (3.6, F4):**
  - A trade is "inside" when its **entry** is within ± the owner's window (default 15 min) of a high-impact event whose currency maps to the trade's instrument.
  - It is "outside" when the trade's date is inside stored coverage, and "No news data" otherwise.
  - Trades are tagged on create, import and edit, again when the window or the map changes, and automatically when coverage grows.
- **Analytics:**
  - The News filter is live: Inside / Outside / No news data, plus by event type.
  - It adds an "Around news" breakdown (trades, win rate, avg R, total R) and an honest coverage note.
  - The CSV export gained news columns.
- **Brief (U7):** stored high-impact events for the next uncovered month, with ok / partial / no-data status.
- **Endpoints:** `/status`, `/events`, `/events/{id}` (history, reactions, summary sentence), `/today` (headline), `/next`, `/week-ahead`, `/timeline`, `/prefs`, `/instrument-map` (admin PUT).
- **Dev seed:** a synthetic week around "now", a year of US CPI and NFP with reactions, weekly claims and ISM releases, and coverage. Seeded trades are tagged.

**Prices** (`services/prices/`, `api/prices.py`, F1/F13)
- **Provider:** a `PriceProvider` protocol with `TwelveDataProvider` and `FakePriceProvider`.
  - The key travels only in the `Authorization: apikey` header and is scrubbed from errors.
  - The fake is used only in development with no key, or when forced. It never writes availability and has its own cache prefix.
- **Per-key minute limiter:** 8 credits per wall-clock minute, which is how Twelve Data counts. Requests **queue** for the next minute. At most 2 may wait per key; any more are served the last known price at once (a security-review fix).
- **Credits:** each user has a daily credit counter (800, resets 00:00 UTC). `/api_usage` corrects it upwards. At the limit the user sees "Live data paused – daily limit reached" with the last known prices.
- **Shared cache:** keyed by symbol (quote 15 min, sparkline 15 min, search 24 h). Credits are charged to whoever's key fetched. `SHARED_CACHE` is a one-line switch to a per-user cache (see Open questions). A "not on your plan" answer is never reused for another user (a security-review fix).
- **Pins:** capped at 8.
- **Endpoints:** search, quote, quotes for pins, sparkline, usage, pin/unpin/order, and settings.
- **Never a fake or substitute price:** if Twelve Data answers an index symbol with an ETF, it is marked "Not available on your Twelve Data plan".
- **Check key** in the vault now calls Twelve Data `/api_usage` (1 credit) and answers e.g. "Key works · 12 of 800 credits used today".
- **Price reactions (3.3):** once per release, at 5 / 15 / 60 minutes, as a range and move in pips or points plus direction.
  - Only keys whose owner turned on "Allow background jobs to use my key" (default off) are used.
  - Each user is capped (default 150 a day), 200 credits are always kept for the watchlist and search, users take turns, and at most 5 series run per tick.

**Push** (`services/push.py`, `services/alerts.py`, `api/alerts.py`, F7)
- Web Push with VAPID through pywebpush. `make vapid` writes the trio into `.env`; `VAPID_SUBJECT=mailto:you@example.com` is a placeholder for Jamie.
- Tables: `push_subscriptions` (per device), `alert_prefs` and `alert_deliveries`.
- **Who gets an alert:** by default 15 minutes before high-impact events, in the currencies of the user's instruments, with optional quiet hours (UK) and an optional chime.
- **Dedupe and pruning:** a dedupe row (unique per device × event) is written before sending. Subscriptions are pruned on 404/410. Alerts more than 10 minutes late are not sent.
- **SSRF guard:** only Google, Mozilla, Apple and Microsoft push hosts are accepted as endpoints, both at registration and at send (a security-review fix).
- `public/sw.js` is hand-written and registered once. It handles `push` and `notificationclick` (opens the event) and nothing else. Offline caching comes in Prompt 5.

**Front end**
- **News Room** (`/news`):
  - **Header:** the logo, a "last updated" line that says when a feed is failing, and Alerts.
  - **Countdown ring for the next high-impact event:** depletes; orange in the last 15 min, red in the last 5, opacity pulse. Once released, the card holds the event for 30 minutes so the actual flips in.
  - **Calendar:** Day / Week / Week ahead, in UK time, today by default. The Week ahead is the default from Sunday 18:00 UK.
    - **Each event:** time, currency, name, impact chip with label, and actual / forecast / previous with surprise (cyan ▲ / violet ▼ with the difference and "Better/Worse than forecast").
    - **Filters:** currency, impact and "my instruments only". In the URL; a bottom sheet on the phone and tablet.
    - **Layout:** rows from 1440 px, and cards grouped by time below that.
  - **Trading-day timeline (3.2):** Asia/London/New York bands, shaded ±window news windows, H/M/L markers, a moving now line and the current session highlighted. On the phone it scrolls sideways with now centred.
- **Event detail** (`/news/events/:id`): a shared-element transition from the list; the explanation and why it matters; release history; price-reaction averages and each release; the summary sentence; honest empty states.
- **Week ahead** (3.4): high-impact events by day with the instruments they move, and the quietest day.
- **Alerts settings** (`/settings/alerts`):
  - iOS "Add to Home Screen" guidance (16.4+).
  - Permission is asked only after a button press.
  - Device list, Send test notification, preferences, and the chime with a sample.
- **Markets components:** `TickerCard` (odometer digits; a green/red wash behind the price that fades over 600 ms with its own ▲/▼ tick glyph; live dot; "Delayed · updated HH:MM"), `InstrumentSearch` (combobox), `WatchlistRow` (swipe to remove on touch, plus a button), `CreditsMeter`, `/markets` (watchlist page) and the instrument view `/markets/:symbol` (ECharts intraday line with crosshair and data table, day stats, the news that moves it). The Hub placement is Prompt 5.
- **Settings:** a News Room card (instruments followed, window size) and a Live prices card (credits meter, background-jobs opt-in). Markets and News alerts are also in the phone More page.
- **Tokens:**
  - `--color-surprise-up` / `--color-surprise-down` (proposed).
  - `--dur-flash` (600 ms).
  - `.price-flash`, `.price-tick`, `.odo-*` and `.flip-in`, each with a Reduced-motion rule.

**Tests:**
- 467 pytest (205 new) + 6 Node.
- 144 Playwright at 1440 and 375 px with axe (32 new in `e2e/news.spec.ts`), including **"the browser never calls Twelve Data (or the news feeds) directly"**.

## Gate 4 checklist

| Check | Result | How verified |
|---|---|---|
| Today's events show in UK time (fixtures) | Pass | `test_news_feeds` (FF 08:30 ET → 13:30 UK in winter, 12:30 UK in the late-October gap week; JBlanked EET/EEST); `test_news_api` today/headline; e2e "today's events in UK time" |
| Today's events, live | Pass | One live Forex Factory fetch into `/tmp/tp-live-ff`: 116 events this week (19 high). Today's NFP, Unemployment Rate and Average Hourly Earnings (08:30 ET) stored at **13:30 UK**. Headline "7 high-impact events today – JPY BOJ Gov Ueda Speaks at 16:00". JBlanked not live (no valid key) |
| The countdown is correct | Pass | `test_news_api` `/next` seconds_until with a frozen clock; live: `/next` → BoJ Ueda 16:00 UK, 3,506 s at 15:01:34 UK |
| The JBlanked lease never allows two calls within 5 minutes | Pass | `test_leases` (slot per interval; 10 concurrent sessions → exactly one wins); `test_news_feeds` (two refreshes a minute apart → one request; daily budget) |
| Trades tagged inside/outside windows; "No news data" outside coverage | Pass | `test_news_tagging` (11): window sizes, NAS100 ← USD, GER40 ← EUR, outside coverage → no data, re-tag when coverage grows / window changes / map edits |
| Analytics News filter works | Pass | `test_analytics_api` news filter and `around_news`; seeded data: "News history covers 105 of 160 trades" |
| Credits counted per user | Pass | `test_prices_service` (two users, separate counters, charged to whoever's key fetched) |
| Cache prevents a repeat call within 15 minutes | Pass | `test_cache_prevents_a_repeat_call_within_15_minutes_and_refetches_after` (counting transport) |
| The 8/min bucket queues requests | Pass | `test_prices_provider`: the 9th waits for the next minute (fake clock), and no more than 2 wait per key |
| The browser never calls Twelve Data (e2e) | Pass | `e2e/news.spec.ts` "the browser never calls Twelve Data (or the news feeds) directly" (both widths) |
| With a Twelve Data key, one live quote works for EUR/USD; XAU/USD, GER40, NAS100 recorded | Pass | Live with Jamie's key (from chat, passed in the environment for one process, never written to a file): see the coverage findings below |
| The scheduler sends a due test alert exactly once | Pass | `test_alerts` (frozen clock: two ticks → one send per device; two schedulers at once → one send; quiet hours; 404/410 pruned) |
| Local "Send test notification" works in Chromium | **Partial** | Every server path is tested with the fake sender. In a real Chrome driven by Playwright, the flow reaches the browser's push registration, which Chrome refuses under automation ("Registration failed – permission denied"), with or without background networking. After two genuine fixes this is logged under Known issues; Jamie's check step 4 covers it |
| `make lint`, `make test`, `make smoke` green; bundle budget | Pass | lint clean (ruff, oxlint, tsc); 467 pytest + 6 Node; **144/144 Playwright**; Hub **187.8 KB** of 200 KB; ECharts stays lazy |
| `/check-devices` clean for News Room, event detail, week ahead, alerts, instrument view at six widths | DEVICES_RESULT | `docs/check-devices/2026-11-06-p4/` (48 screenshots, not committed) |
| design-reviewer: no blockers or majors | DESIGN_RESULT | Pass 1: 0 blockers, 11 majors, all fixed (tick glyph, credits wording, H/M/L markers, laptop rows, duplicate transition names, Reduced odometer, search focus, stale-on-refresh-error, instrument-news error, More entries, ECharts intraday chart) plus 17 minors |

## Twelve Data coverage (live, Jamie's Basic key, 6 Nov 2026 ~15:00 UK)

| Instrument | Symbol tried | Answer | Shown in the portal |
|---|---|---|---|
| EUR/USD | `EUR/USD` | ✓ "Euro / US Dollar", Forex, 1.11468, market open | Live price |
| XAUUSD | `XAU/USD` | ✓ "Gold Spot / US Dollar", Forex, 4,045.23. **Available on Basic**, although the pricing page lists commodities from Grow | Live price |
| GER40 | `DAX` | Answers with the **Global X DAX Germany ETF** (NASDAQ, 44.16), not the index | "Not available on your Twelve Data plan" (the ETF is never shown as GER40) |
| NAS100 | `NDX` | 403: plan | "Not available on your Twelve Data plan" |

`/api_usage` afterwards: 15 of 800 credits used today, plan "basic", minute limit 8.

**Credit cost per endpoint** (docs, confirmed by the live run's charges): `/quote`, `/price`, `/time_series`: 1 per symbol (a batch of 4 symbols cost 4); `/symbol_search`: 1 per request; `/api_usage`: **1** (not free); limits 8 per minute (the window resets at :00) and 800 per day (00:00 UTC). With 8 pins, a quote plus a sparkline each 15 minutes is 16 credits per refresh, so a full day of a visible watchlist is about 12.5 hours of the 800 (see Open questions).

## JBlanked history coverage achieved

**None yet: 0 days.**
- The `321175` given in chat is not an API key. JBlanked keys are 30+ characters; that number looks like an account id.
- `make news-backfill` stops with "The JBlanked key looks too short to be valid".
- JBlanked's current pricing (changelog, 18 Sep and 2 Oct 2026): free use is **1 request per day, on `/calendar/today/` only**. Week, range and history requests cost credits. So even with a valid key, the free tier gives each day's actuals (fetched once at 21:15 UK) but **no backfill**.
- Coverage today is the Forex Factory weeks stored from now on. Backtests on earlier dates show "No news data", as designed (F4).

## Assumptions

1. **Surprise colours:** `--color-surprise-up` cyan `#5CC8FF` (9.4:1) and `--color-surprise-down` violet `#A78BFA` (6.5:1), never win/loss. They are always paired with ▲/▼ and the difference. The wording ("Better/Worse than forecast") comes from each event type's `higher_is_better`, from the currency's point of view (higher CPI = better for the currency; higher unemployment = worse). Both colours are **proposed**.
2. **Entry time** decides inside/outside a news window, not the whole holding period. Otherwise multi-day swing trades (the sample averages 1 d 16 h) would almost all count as "inside". Only high-impact events make windows.
3. **JBlanked:**
   - Uses the `forex-factory` source.
   - Times are read as Europe/Athens (inferred from the docs' "GMT+2" and the clients' offsets; confirm against a live response).
   - **Default budget is 1 request a day** (21:15 UK), because that is the free tier. The Prompt's "1 per 5 minutes" is kept as the global minimum spacing.
   - Raise `TRADING_PORTAL_JBLANKED_DAILY_REQUESTS` if credits are bought; the scheduler then also fetches within 20 minutes after a high-impact release.
4. **Forex Factory** retries 15 minutes after a failure. Rows the feed drops are deleted unless they hold an actual, a JBlanked match or reactions.
5. **Prices:**
   - Shared cache across users as asked (`SHARED_CACHE = True`).
   - "Not on your plan" refusals are per user.
   - Background reactions keep 200 credits back for the watchlist and search and skip (never wait) when the minute is full.
   - New users start with an empty watchlist and a row of suggestions.
   - The phone refreshes every 30 minutes, desktop every 15, and only while the tab is visible.
6. **Alerts:**
   - Currencies default to "the currencies of my instruments".
   - An alert more than 10 minutes late is dropped.
   - Quiet hours are UK time and may wrap midnight.
   - Deactivated users get none.
   - The title uses the feed's own title ("USD CPI m/m in 15 min").
7. **VAPID:** the private key is the raw 32-byte value, urlsafe base64 (the format `web-push` prints and `py_vapid` reads). The public key served is derived from the private one.
8. The News Room's violet identity appears only on its logo. Working UI uses the accent and the reserved meanings.
9. The countdown ring and news windows use impact orange and red, as Foundations "News countdown" and 3.2 describe.
10. The keys pasted in chat were **not** written to `.env`; the permission check refused that. The Twelve Data key was used once, in the environment of a single process, for the live check.

## Open questions for Jamie

1. **JBlanked key:** paste the real 30+ character key from jblanked.com/api/key into `.env` / Fly. Do you want to buy JBlanked credits for history (backfill) and same-hour actuals, or stay on the free one-a-day actuals?
2. **Twelve Data terms:** Basic is "internal non-display", and the terms forbid redistributing data. The shared cache serves one user's fetched price to the others. Keep it shared (current), or flip `SHARED_CACHE` to per-user, which costs everyone more credits?
3. **GER40 and NAS100** aren't on Basic (DAX resolves to a US ETF; NDX is refused). Options:
   - leave them "Not available" (current);
   - show clearly labelled ETF proxies (EWG/DAX ETF, QQQ);
   - use a paid plan.
4. **Surprise colours:** keep cyan ▲ / violet ▼? Cyan is also the second chart series, and the violet sits near the News Room violet.
5. **Credit budget:** 8 pins with sparklines use ~64 credits an hour while visible. Cache sparklines for 60 minutes, or keep 15?
6. Set `VAPID_SUBJECT` to your own `mailto:` address (push services use it to contact the sender).
7. Is the entry-time rule right for "inside a news window", or should a trade held through high-impact news count too?
8. Should alerts also go out for medium impact by default, or stay high only?
9. Should the Week ahead include medium-impact events, or stay high only (current)?

## Known issues

- **Real-browser push not verified end to end.** Chrome under Playwright refuses push registration, and the in-app browser pane blocks notifications. The server side (VAPID signing, dedupe, pruning, payload) is covered by tests with a fake sender. Jamie's check step 4 does it for real.
- **JBlanked never called live** (no valid key). Its response shape and timezone come from the docs and the client source; the first live response should be recorded as a fixture.
- Design-review minors left open:
  - same-minute timeline markers stack (no grouping popover);
  - the countdown isn't sticky on the phone (the actual shows inline there);
  - Card subtitles aren't `.num`;
  - switches aren't optimistic;
  - no extra side panel at 1920+;
  - the loss-red toast tone is used for non-loss notices (existing convention).
- In development, the Hub's News card is still the Phase 1 placeholder; Prompt 5 places `TickerCard` and today's news there.
- **The dev server's feeds run live** (`make dev` with the default `TRADING_PORTAL_FEEDS=live`). That is one Forex Factory request an hour; set `TRADING_PORTAL_FEEDS=off` to stop it.

## Production secrets needed

| Secret | Used for |
|---|---|
| `TRADING_PORTAL_SECRET_KEY` | Vault key derivation (as before) |
| `JBLANKED_API_KEY` | Actuals (and history if credits are bought) |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` | Web Push (`make vapid` makes a pair; set your own `mailto:`) |
| *(none for Twelve Data)* | Each user pastes their own key in Settings (F1) |

`fly.toml` now keeps one machine always on (F7). Nothing was deployed and no Fly secrets were set.

## Jamie's check (10 min)

1. `make dev`, sign in, go to **Settings → API keys**:
   - paste your Twelve Data key and click **Check key**: "Key works · N of 800 credits used today";
   - in **Live prices**, leave background jobs off for now.
2. **Markets** (sidebar, or More on the phone):
   - pin EUR/USD, XAU/USD and BTC/USD: each card shows a price, ▲/▼ change, day high/low, a sparkline and "Delayed · updated HH:MM";
   - pin GER40: "Not available on your Twelve Data plan";
   - open EUR/USD for the instrument view (chart, day stats, the news that moves it).
3. **News Room:**
   - the countdown shows the next high-impact event;
   - today's events are in UK time;
   - click **High** and **USD** (Filters on the phone);
   - open an event for its explanation, history and reactions;
   - try **Week**, **Week ahead** and the timeline (sideways on the phone).
4. **Alerts (after deploy, on your iPhone):**
   - open the portal in Safari → Share → **Add to Home Screen**, then open it from the Home Screen;
   - **Settings → Alerts** → **Turn on alerts on this device** → Allow → **Send test notification**: a notification arrives, and tapping it opens the portal.
   - On the Mac first: Chrome or Safari at localhost works too once `make vapid` has written the keys (already done in your `.env`; change `VAPID_SUBJECT`).
5. In a strategy's **Analytics**, use the **News** filter: Inside / Outside / No news data. Your real backtests will mostly say "No news data" until history exists (F4).
6. Add to `.env` yourself:
   - `DEV_TWELVE_DATA_KEY=<your key>` (optional, development only);
   - `JBLANKED_API_KEY=<the 30+ character key>`.
