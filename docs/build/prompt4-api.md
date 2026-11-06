# Prompt 4 API contract (News Room, prices, alerts)

The shared contract between the backend slices and the front end. JSON field names are exact. Times are
ISO 8601 UTC (`2026-11-06T13:30:00Z`) unless the field name says `uk_`. Every endpoint needs a signed-in
user (`CurrentUser`); writes need the CSRF header as usual. Admin-only endpoints say so.

## News — `/api/news` (router `app/api/news.py`)

`EventOut`
```
{ id, title, name,               // name = canonical event-type name, else the feed title
  currency, at, uk_date, uk_time, // uk_date "2026-11-06", uk_time "13:30" (Europe/London)
  all_day, impact,               // "high" | "medium" | "low" | "holiday" | "none"
  impact_label,                  // "High" | "Med" | "Low" | "Holiday" | "None"
  forecast, previous, actual, revised,   // strings as published, or null
  released,                      // actual is known
  surprise: null | { direction: "up" | "down" | "inline",
                     diff: number, diff_text: "+0.2" | "−15K",
                     better: true | false | null,       // from event_types.higher_is_better
                     wording: "Better than forecast" | "Worse than forecast" | "In line with forecast" | "Above forecast" | "Below forecast" },
  instruments: ["XAUUSD", ...],  // mapped instruments (news_instrument_map)
  mine: bool,                    // touches one of the viewer's followed instruments
  event_type_id, has_explanation }
```

| Method | Path | Answer |
|---|---|---|
| GET | `/status` | `{ last_updated_at, feeds: [{ feed, last_success_at, last_attempt_at, last_status, last_error }], coverage: [{ source, start_date, end_date }], jblanked: { configured, requests_today, daily_budget, next_slot_at } }` |
| GET | `/events?from=&to=&currencies=USD,EUR&impacts=high,medium&mine=1` | UK dates, inclusive; default today. `{ events: [EventOut], from, to, last_updated_at, window_minutes, my_instruments }` |
| GET | `/events/{id}` | `{ event: EventOut, type: null \| { id, name, category, explanation, why_it_matters, higher_is_better }, history: [{ event_id, at, actual, forecast, previous, surprise }], reactions: [{ instrument, unit, releases, average_range: {"5": n\|null, "15":…, "60":…}, rows: [{ event_id, at, horizons: {"5": { status, range, move, direction }, "15":…, "60":…} }] }], summary: string \| null, empty: { history: string \| null, reactions: string \| null } }` |
| GET | `/today` | `{ headline, high_count, events: [EventOut], last_updated_at }` — the viewer's instruments only. Headline e.g. "3 high-impact events today – USD CPI at 13:30", or "No high-impact news today." |
| GET | `/next?mine=1` | `{ event: EventOut \| null, seconds_until, server_now }` — next high-impact event (default the viewer's instruments). |
| GET | `/week-ahead?start=` | `{ start, end, default_view, days: [{ date, label, events: [EventOut] }] }` — high impact only. Without `start`: this Mon–Fri, or next week from Sunday 18:00 UK (`default_view` true then). |
| GET | `/timeline?date=` | `{ date, window_minutes, sessions: [{ name: "Asia" \| "London" \| "New York", start, end }], events: [EventOut], windows: [{ event_id, start, end }] }` — sessions in UK time (Asia 00–08, London 08–16:30, New York 13:30–21:00 UK). |
| GET | `/prefs` | `{ instruments, news_window_minutes, available: [{ code, name }] }` |
| PATCH | `/prefs` | body `{ instruments?, news_window_minutes? }` → as GET. Re-tags the viewer's trades. |
| GET | `/instrument-map` | `[{ currency, instrument }]` |
| PUT | `/instrument-map` (admin) | body `[{ currency, instrument }]` → replaces; re-tags every trade |

Analytics (`POST /api/analytics/query`): `filters.news` is `"inside" | "outside" | "no_data" | null` and
`filters.news_event_types: string[]` (event-type names). The answer's `news_status` is `"ok" | "partial" | "no_data"`,
`notes.news` explains, and `backtest.around_news` / `ideal.around_news` is a breakdown
`[{ key: "Inside news window" | "Outside" | "No news data" | <event type>, trades, win_rate, avg_r, total_r }]`.

Trades (`TradeOut`) gain `news_status: "inside" | "outside" | "no_data"` and `news_events: [{ event_id, name, currency, at, minutes_from_entry }]`.
Brief (`GET /api/strategies/{id}/brief`) fills `news: { month, status: "ok" | "partial" | "no_data", high_count, events: [EventOut] (high impact, max 40), note }`.

## Prices — `/api/prices` (router `app/api/prices.py`)

Symbols are query parameters (`EUR/USD` has a slash). `symbol` accepts our code (`XAUUSD`) or a provider symbol.

`QuoteOut`
```
{ symbol, code, name, unit, decimals,
  status: "ok" | "stale" | "unavailable" | "no_key" | "error",
  price, change, percent_change, open, high, low, previous_close,   // numbers or null
  is_market_open, market_time,     // provider's bar time
  updated_at,                      // when we fetched it (cache time) — "Delayed · updated HH:MM"
  message }                        // e.g. "Not available on your Twelve Data plan"
```
`UsageOut` `{ provider: "twelve_data" | "fake", has_key, used, limit, background_used, background_cap, allow_background_jobs, resets_at, paused, paused_reason }`

| Method | Path | Answer |
|---|---|---|
| GET | `/search?q=` | `{ results: [{ symbol, code, name, exchange, type, available }], cached }` (24 h cache) |
| GET | `/pins` | `{ pins: [{ symbol, code, name, position }], max: 8 }` |
| POST | `/pins` | body `{ symbol }` → 201 pin; 409 at 8 |
| DELETE | `/pins?symbol=` | `{ ok }` |
| PUT | `/pins/order` | body `{ symbols: [] }` |
| GET | `/quotes` | `{ quotes: [QuoteOut], usage: UsageOut, refresh_seconds }` for the viewer's pins |
| GET | `/quote?symbol=` | `QuoteOut` |
| GET | `/sparkline?symbol=` | `{ symbol, status, interval, points: [{ t, v }], updated_at }` |
| GET | `/usage` | `UsageOut` |
| PATCH | `/settings` | body `{ allow_background_jobs?, background_daily_cap? }` → `UsageOut` |

The vault's `POST /api/me/keys/twelve_data/test` calls Twelve Data `/api_usage` (1 credit) and returns `{ ok, tested_at, message }`.

## Alerts — `/api/alerts` (router `app/api/alerts.py`)

| Method | Path | Answer |
|---|---|---|
| GET | `/config` | `{ push_configured, vapid_public_key }` |
| GET / PUT | `/prefs` | `{ enabled, minutes_before, currencies (null = my instruments'), effective_currencies, impacts, quiet_start, quiet_end, chime }` |
| GET | `/devices` | `[{ id, device_label, created_at, last_success_at, last_error, endpoint_hash }]` |
| POST | `/subscriptions` | body `{ endpoint, keys: { p256dh, auth }, device_label }` → 201 `{ id }` (upsert on endpoint) |
| DELETE | `/subscriptions/{id}` | `{ ok }` (own only) |
| POST | `/test` | body `{ subscription_id? }` → `{ sent, failed, pruned }` |

Push payload (what `sw.js` receives): `{ title, body, url: "/news/events/{id}", tag: "event-{id}", event_id, chime }`.

## Front-end routes
`/news` (calendar; week ahead by default from Sunday 18:00 UK), `/news/week`, `/news/events/:id`,
`/news/timeline` (inside `/news` on desktop), `/settings/alerts`, `/markets/:symbol` (instrument view).
