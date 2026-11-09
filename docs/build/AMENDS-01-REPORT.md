# Amends 01 — initial feedback (9 Nov 2026)

Source: Jamie's "TradingPortal Feedback" PDF plus one follow-up message. Branch `amends/01-initial-feedback`.

| # | Feedback | What changed |
|---|---|---|
| 1 | Team calendar is redundant (follow-up: the whole Calendar tool) | Calendar removed from the Hub, sidebar, phone tabs, command palette and routes (`/calendar` now redirects to the Hub). Its pages, `lib/calendar.ts`, CSS and the FullCalendar packages are gone. The backend `/api/calendar/*` API and the `tasks` tables are left in place (no migration), so nothing is lost if it's ever wanted back. |
| 2 | Login logo stretched on a large screen | The flex column stretched the `<img>` to full width at a fixed height. `Logo` now carries its intrinsic size, `self-start` and `object-contain`, so it keeps its aspect ratio everywhere (checked at 1280, 1920 and 2560 px wide). |
| 3 | News Room: moving the day forward still said "Today" and showed no forecasts | The date control now names the day or week on screen (Today / Tomorrow / "Thu 12 Nov") with a separate Today button. Root cause of the empty future days: only Forex Factory's *this week* file was fetched, and it only rolls over on Sunday. Next week's file (`ff_calendar_nextweek.json`, setting `ff_calendar_next_url`) is now fetched too, on its own hourly run (`forex_factory_next`; a 404 is logged as skipped). The Week ahead rolls forward from Friday 21:00 UK instead of Sunday 18:00. Days past the published schedule say so instead of "No events". |
| 4 | Replay Journal: $ P&L should be the most visible metric | Backtest analytics lead with a full-width Net P&L tile ($, with R underneath); Max drawdown and Expectancy show $ with R beneath; equity curve and drawdown default to $; breakdowns default to Net $; rulebook groups, owner split, Around news, the trade mini-list, trade list (phone and table), trade detail, strategy cards, session recap and the Hub's weekly recap all put $ first. Ideal-trade views and Compare stay in R (ideal trades are measured in R). |
| 5 | Hub header: greeting, date and market state in large type; time and zone in a small box | The h1 is now three lines: "Good evening, Jamie." / "Today is Monday 9th November." / the market state. The clock sits in a small bordered box with "London · GMT/BST". |
| 6 | Calendar: future news and international bank holidays | Future news: see 3. Bank holidays come from the `holidays` library (new dependency), one centre per currency (US, Euro area TARGET, England, Japan, Sydney, Canada, Zurich, New Zealand, China), weekdays only. They show in the News Room Day and Week views ("Bank holidays" panel) and on each Week ahead day, and are known years ahead. |

## Tests
- Backend: 729 passed (new: next-week feed, 404 skip, switch-off, weekend roll-over of the week ahead, holidays on events and week ahead).
- Frontend: tsc, oxlint, build; Hub initial JS 192.6 KB gzip (budget 200).
- e2e (Playwright, desktop + phone, 244 tests): all pass except `hub.spec.ts` "a modifier click on an island is a plain link", which fails the same way on the pre-amends build in the Linux sandbox (Ctrl-click popup reports about:blank), so it isn't caused by these changes. Specs updated for the removed calendar (calendar spec deleted; hub, keyboard, routes, csp, zoom, offline adjusted) and the $ headline (analytics, csp).
- Also fixed while testing: on days with releases minutes apart (e.g. Monday 14:45 + 15:00), the News Room timeline's 44px markers overlapped and failed WCAG 2.5.8. Releases within 30 minutes now share one marker that opens the most important one and names them all.

## Open questions
- `ff_calendar_nextweek.json` couldn't be fetched from the build sandbox (network allowlist), so it is untested against the live publisher. If it 404s in production the run is logged as skipped and the app behaves as before; check the News Room status feed after deploy.
- Hub "Personal bests" stays process-based ("not profit") as designed; say if that should show $ too.
