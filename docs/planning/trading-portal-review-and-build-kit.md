# Trading Portal Foundations: Review & Build Kit

Nov 5, 2026 · @Jamie

A review of [Trading Portal Foundations](https://claude.ai/artifact/1mZQfVkYcQWed5hfR6ZbZw) by four research lanes — critic, GitHub scout, Claude tools scout and UX lab — checked by a fresh-eyes reviewer. Nothing in the Foundations doc was edited; each proposed fix is a comment there for you to approve.

## Top 10 actions

Updated 5 Nov with your decisions and a read of the existing repo. The current Replay Journal already has the FX Replay importer, analytics, coverage tracker, AI export and sign-in, so the work is extending and re-skinning it, not starting again. Ranked by impact ÷ effort.

1. **Keep the FastAPI + React repo as the base and re-skin it to the new look**: importer, metrics, coverage, export, auth and sharing are already built. *Critic + Repos · —*
2. **Per-user Twelve Data keys**: each user pastes their own free key (800 credits/day); stored encrypted server-side, with a per-user credit meter and cache (F1, F13). *Critic · S–M*
3. **Add admin/member roles, invite links and Deactivate** to the existing sign-in, with server-side checks that members edit only their own work; no strategy duplication (F6, F11, F12). *Critic · M*
4. **Build the bulk screenshot matcher first**: you upload FX Replay `/screenshot` files after the CSV import, so drop them all at once and match to trades (U3). *UX · M*
5. **Encode the unlock rule in the coverage tracker**: 6+ trades in total across 6 consecutive months (F9). *Critic · S*
6. **Set breakeven to ±2 of zero** (assumed $) as the default threshold everywhere (F16). *Critic · S*
7. **Run the masterprompt** to install Playwright MCP, frontend-design, Context7 and the rest. *Tools · S*
8. **Litestream to Tigris** for off-machine backups of the database and screenshots, on one small always-on machine that also sends the push alerts (F2, F5, F7). *Critic + Repos · M*
9. **Free-only news tagging**: tag backtests where JBlanked history exists and mark the rest "No news data"; no Apify (F4). *Critic · S*
10. **One shared ICT/SMC tag vocabulary** with synonyms, plus the structured reasoning template (U5). *UX · M*

## Doc fixes

Nineteen fixes, each left as a comment (F1–F19; 12 have a 5 Nov update reply) on the exact line in the Foundations doc; the doc text is unchanged. F1–F3, F5, F6 and F8 need settling before code; F4 and F7 can wait for roadmap Phase 5.

| # | Section | Issue | Proposed rewrite (short) |
| --- | --- | --- | --- |
| F1 | 1.5 Live market data | Twelve Data Basic is "internal non-display"; XAU is a Grow-plan asset; GER40 unconfirmed | Confirm display rights, XAU/USD and GER40 in writing; put prices behind one swappable PriceProvider |
| F2 | 4.2 Tech stack and hosting | Stack never named; fly.io no longer has a free allowance for new orgs; Managed Postgres $38/mo | Name the stack; one small machine, SQLite on 1GB volume, screenshots in Tigris; target under $5/mo (waived). It stays always on, as today, because v1 push alerts need it; still within the waiver |
| F3 | 2.3 Backtest tab | The core CSV import has no spec | Column map from a real export, CSV timezone per strategy, Import Session with undo, duplicate key, preview step, destination switch (Ideal winners only / Backtest) |
| F4 | 3.6 Link to the Replay Journal | Backtests are on past dates; news history only builds forward, so tagging would be empty | Load JBlanked event history once; tag "News data unavailable" outside it; paid, one-off, optional Apify backfill if history is short |
| F5 | 2. Replay Journal (intro) | No backup, restore, archive or delete | Litestream to object storage, quarterly restore test, 30-day Trash, admin "Export everything" |
| F6 | 4.1 Users, roles and sharing | No login method, reset or removal rule | Invite link, password + optional passkey, lockout, admin reset; Deactivate (not delete) a mate; server-side checks |
| F7 | On the phone like an app | Push promised here; 3.5 and 4.2 say later; scale-to-zero can't send pushes | Decided for v1: Web Push to the installed portal (iOS 16.4+, Android), sent by an in-app scheduler on the always-on machine; no external cron |
| F8 | 2.4 Analytics tab | AI-ready export missing entirely | New 2.5 "Export for AI": zip of trades.jsonl, images, strategy.md, README\_prompt.md, manifest.json + "Copy for AI" |
| F9 | 2.3 Backtest tab | Unlock rule stated three different ways | Coverage = months by market date with ≥1 trade; unlock = 6 consecutive; one rule everywhere |
| F10 | 2.2 Ideal Trades tab | "screenshot(s)" vs two shots per trade | Entry and Exit slots + 3 extras; WebP made in the browser, \~1920px full + 400px thumbnail (\~250KB a shot); missing-screenshot badge |
| F11 | 1.4 Team calendar | "Solo use first" contradicts 4.1 roles | Multi-user from release one; owner\_id on every record |
| F12 | 4.1 Users, roles and sharing | "Shared" is unclear; merged curves mislead | Mine · Everyone · Others; "Split by owner" in Analytics |
| F13 | 1.5 Live market data | 10-min refresh vs "live" motion; 4 users ≈ 1,440 credits | Union of pins capped at 8; 15-min refresh while the Hub is open; "Delayed · updated" label |
| F14 | 1.3 App launch islands | 1–1.5s fixed vs "\~600ms minimum, exit when ready" | Minimum \~600ms, exit when ready, 250ms after first visit |
| F15 | Loading screens and states | No error, read-only, offline or first-run states | Five required states per screen + Hub first-run checklist |
| F16 | 2.4 Analytics tab | "Close to FX Replay" not written down | List FX Replay's metric set (BE threshold, by hour, streaks, calendar…) plus browser Monte Carlo and a Reconcile line against FX Replay's totals, with formula tooltips |
| F17 | Brand marks | Head-tag code block is corrupted | Re-paste favicon, manifest (display: standalone) and og:image tags |
| F18 | Motion › Build notes | Two animation libraries + Lottie = heavy | View Transitions with fallback; Motion only; inline SVG loaders; \~200KB Hub JS budget |
| F19 | 1.2 Today's news overview | Your sessions include NAS100, which isn't in the instrument list or the event mapping | Add NAS100; map USD events to it in 3.1 |

## Build kit (repos)

The current Replay Journal is FastAPI + SQLAlchemy/Alembic + SQLite, with a React 19 + Vite + Tailwind 4 front end that already uses ECharts, Lightweight Charts, Radix and Playwright, so most of this kit slots straight in. Better Auth does not: it is JavaScript-only. Stars and last-commit dates checked 5 Nov 2026 (stars approximate).

| Repo | Replaces in the doc | Licence | Stars | Last commit | Stack | Fit |
| --- | --- | --- | --- | --- | --- | --- |
| [Apache ECharts](https://github.com/apache/echarts) | All charts: equity curve in R, distributions, entry-time heatmap, P&L calendar | Apache-2.0 | \~67k | 2026-10-04 | TS, canvas/SVG | 5 — already chosen; import from `echarts/core` (tree-shaken) and lazy-load off the Hub |
| [Better Auth](https://github.com/better-auth/better-auth) | 4.1 users and roles (admin plugin, access control, sign-up off) | MIT | \~29.5k | 2026-11-05 | TS; SQLite/Postgres via Drizzle, Prisma, Kysely | 1 — your backend is FastAPI; extend the existing users table instead |
| [FullCalendar](https://github.com/fullcalendar/fullcalendar) (standard) | 1.4 team calendar: views, drag, recurrence (rrule), owner colours, news markers; phone uses list/day view with long-press drag | MIT (Premium is paid; not needed) | \~20.6k | 2026-11-03 | TS; React/Vue/vanilla | 5 — closest free Teamup match |
| [shadcn/ui](https://github.com/shadcn-ui/ui) | Layout and components: one dark design system, CSS-variable tokens | MIT | \~127k | 2026-11-04 | React, Tailwind, Radix | 5 if React |
| [Litestream](https://github.com/benbjohnson/litestream) | 4.2 backups: streams SQLite to Tigris/S3, restore on boot; stops with the machine | Apache-2.0 | \~14.4k | 2026-11-03 | Go binary, any app | 5 |
| [echarts-for-react](https://github.com/hustcc/echarts-for-react) | React wrapper for ECharts (Vue: [vue-echarts](https://github.com/ecomfe/vue-echarts)) | MIT | \~5.0k | 2026-01-21 | React | 4 |
| [Konva](https://github.com/konvajs/konva) + [react-konva](https://github.com/konvajs/react-konva) | Screenshot markup (arrows, boxes, text) on Entry/Exit shots | MIT | \~14.9k / \~6.4k | 2026-11-05 / 2026-10-14 | TS canvas | 4 — small brand-styled annotator in 1–2 days |
| [Lightweight Charts](https://github.com/tradingview/lightweight-charts) | Candles in 1.5 and 3.3 price reactions | Apache-2.0 **+ TradingView attribution required** | \~17.8k | 2026-11-05 | TS canvas | 4 — only if real candles are wanted |

**Alternatives considered** (all MIT unless noted, checked 5 Nov 2026): [Event Calendar](https://github.com/vkurko/calendar) (lighter calendar, no recurrence), [Mantine](https://github.com/mantinedev/mantine) (packaged React kit — pick it or shadcn), [Tabler](https://github.com/tabler/tabler) (if the app is server-rendered), [Filerobot Image Editor](https://github.com/scaleflex/filerobot-image-editor) (ready-made but heavy annotator), [JB-News](https://github.com/jblanked/JB-News) (Python JBlanked client), [Deltalytix](https://github.com/hugodemenez/deltalytix) (**CC BY-NC — study only**). [PocketBase](https://github.com/pocketbase/pocketbase) was archived on GitHub on 26 Oct 2026 and clashes with the Better Auth + Litestream choice.

**Nothing good exists for:** an FX Replay CSV parser, a web MT5/TradingView export parser, a maintained JS trade-stats library (win rate, expectancy, R drawdown), a Forex Factory JSON client, or a current fly.io SQLite template. Each is small custom code. **Left out:** TradeNote (GPL-3.0, no commits since Apr 2025), tldraw (paid production licence), marker.js (linkware), Schedule-X (drag-and-drop is paid), Auth.js and Lucia (folded into Better Auth / deprecated), self-hosted Supabase (too many containers to stay free), Tremor and cal-heatmap (stale).

## Claude skills and tools

The first five are worth installing before the first screen is built; all are free or have a usable free tier. Install commands are for Claude Code; a masterprompt that installs and verifies all of them is in the repo at docs/claude-setup/MASTERPROMPT.md.

| Tool | What it does for this project | Cost | Install |
| --- | --- | --- | --- |
| [Playwright MCP](https://github.com/microsoft/playwright-mcp) (Microsoft) | Claude opens each screen at 360, 375, 430, 768, 1440 and 1920px and screenshots it — the Devices "definition of done" | Free (Apache-2.0) | `claude mcp add playwright npx @playwright/mcp@latest` |
| [frontend-design skill](https://github.com/anthropics/skills) (Anthropic) | Steers screens away from generic AI UI; fits Look and feel and Motion | Free | `/plugin install frontend-design@claude-plugins-official` |
| [Context7 MCP](https://github.com/upstash/context7) (Upstash) | Current docs for ECharts, Motion, Better Auth, FullCalendar, fly.io — fewer made-up APIs | Free: 1,000 calls/month | `/plugin install context7@claude-plugins-official` (free key at context7.com) |
| [flyctl MCP](https://fly.io/docs/flyctl/mcp-server/) (Fly.io) | Claude reads logs, checks scale-to-zero, sets secrets and volumes (4.2, 3.7) | Free (in flyctl) | `fly mcp server --claude --server flyctl` — experimental; keep permission prompts on |
| [GitHub MCP server](https://github.com/github/github-mcp-server) (GitHub) | Turns the build order into issues and PRs; runs the screenshot-test workflow | Free | `/plugin install github@claude-plugins-official` — use a fine-grained token for this repo only |
| [Claude Code hooks, subagents, project skills](https://code.claude.com/docs/en/hooks) | A Stop hook runs the Playwright suite; a design-reviewer subagent checks "What to avoid"; a project skill holds the design and motion tokens | Free | `.claude/settings.json`, `.claude/skills/<name>/SKILL.md` |
| [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp) (Google) | Optional. Performance traces for chart morphs and number rolls; confirms the price cache stops repeat Twelve Data calls | Free | `/plugin install chrome-devtools-mcp@claude-plugins-official` (server arg `--no-usage-statistics`) |
| [example-skills](https://github.com/anthropics/skills): webapp-testing, skill-creator | End-to-end tests of CSV import and screenshot upload; builds the design-token skill | Free | `/plugin marketplace add anthropics/skills` then `/plugin install example-skills@anthropic-agent-skills` |
| [security-guidance, code-review, typescript-lsp](https://code.claude.com/docs/en/discover-plugins), pyright-lsp (Anthropic) | Reviews login, roles and uploads (4.1); type errors after each edit | Free | `/plugin install security-guidance@claude-plugins-official` (same for the others) |
| [Sentry](https://sentry.io/pricing/) + [Sentry MCP](https://github.com/getsentry/sentry-mcp) | Later. Error tracking for feeds (3.7) and phones; 1 uptime + 1 cron monitor | Free Developer plan, 1 user, 5k errors | `/plugin install sentry@claude-plugins-official` — MCP on the free plan unconfirmed |
| [shadcn MCP](https://ui.shadcn.com/docs/mcp) | Adds tabs, dialogs, tables and the view toggle fast | Free | `pnpm dlx shadcn@latest mcp init --client claude` — React + Tailwind only |
| dataviz skill (already in your account) | Consistent chart colours and specs in dark mode | Free | Already installed |

**Nothing good exists for:** a free economic-calendar MCP (the only one scrapes Forex Factory, which 3.7 rules out — call the FF feed and JBlanked directly), or a free MCP with index or GER40 history (the Twelve Data MCP has no indices and API coverage of GER40 is unconfirmed (F1); Alpha Vantage's free tier is 25 calls a day). Skip the archived `@modelcontextprotocol/server-github` and `server-postgres` packages.

## New ideas

Four Musts, all aimed at the loop you actually run: one FX Replay session, \~10 trades, CSV, then two screenshots and a reason per trade. Grounded in FX Replay's help pages (its journal notes and screenshots can't be exported, so the portal is the only place they live together) and proven patterns from TradeZella, Tradervue and Edgewonk.

| # | Idea | What it is | Attaches to | Priority | Effort |
| --- | --- | --- | --- | --- | --- |
| U1 | Session record + inbox | Each upload becomes a Session (strategy, CSV timezone, replayed dates, trade count); a strategy-page inbox shows "10 trades · 14/20 screenshots · 6/10 reasons" and "Finish annotating" | 2.1, 2.3 | Must | M |
| U3 | Bulk screenshot matcher | Drop all 20 images at once; paired by filename (`T03_entry.png`) or macOS capture time; a trades × Entry/Exit grid to fix before saving; runs in the browser. Phone: multi-select from Photos, matched by capture time, shown as a list | 2.3, Touch/mouse/keyboard | Must | M |
| U4 | Annotate mode | Full-screen "Trade 3/10" stepper: Cmd+V fills Entry, then Exit, then Reason, then moves on; J/K next/previous; camera-roll pickers on phone | 2.2 entry form | Must | S |
| U5 | Structured reasoning + tag vocabulary | Per-strategy template (HTF bias, draw on liquidity, PD array/entry model, killzone, confluences, invalidation) and one admin-managed tag list with synonyms (FVG = fair value gap) | 2.2, 2.4, 4.1 | Must | M |
| U7 | Pre-session brief | "Start session" opens: strategy profile, rule checklist, last 2 sessions' "one thing to improve", the next uncovered month to replay, and stored news for that period | 2.1, 2.3 | Should | M |
| U9 | Strategy rulebook checklist | 4–8 rules per strategy ticked on every trade; analytics show R with all rules kept vs any broken, and each rule's cost in R | 2.3, 2.4 | Should | M |
| U10 | Excursion: R left on the table | Optional MAE/MFE fields (read off the chart in Annotate mode); exit efficiency = realised R ÷ max favourable R; computed from candles later if credits allow | 2.4 Compare view | Should | M |
| U11 | Auto-insights card | After each import, top 3 differences vs baseline ("Mondays: SL 30% tighter, n=9 · early signal"); min 8 trades per slice; plain SQL, no background job | Session recap, 2.4 | Should | M |
| U13 | Missed / skipped setups | "Saw it, didn't take it": one shot + reason; out of P&L, counted in adherence | 2.3 | Could | S |
| U14 | Flashcard review | Phone swipe-through of ideal trades: entry shot only, call direction and model, tap to reveal exit and R; hit rate per strategy | Key screens on mobile | Could | M |

U10 is M with manual entry, L if computed from candles. Four lab ideas were folded into doc fixes rather than listed twice: import preview (F3), FX Replay parity pack (F16), AI export bundle (F8) and screenshot compression (F10).

## Suggested build order

Build the journal loop (Phase 2) before the Hub: it is what you use after every session, and the Hub's tiles need its data to show anything.

&#91;embedded content: Build order · 6 phases, 5 gates\]

Each gate is a check you can do in an afternoon; nothing moves on until it passes. Phase 4 can start in parallel with Phase 3 once Phase 1 is done.

## Decisions

Your answers from 5 Nov; all questions are now settled.

| Question | Your decision | What it changes |
| --- | --- | --- |
| Fresh start or move the repo? | Moved into Desktop/Trading Portal; new look, same code base | Build kit fits FastAPI + SQLite + React/Vite; Better Auth dropped |
| Twelve Data display rights | Each user enters their own free API key (800 credits/day) | F1, F13: per-user keys, meters and caches; no shared budget |
| FX Replay CSV | Confirmed by your 8-trade NAS100 file (02/11/26), same 22 columns as the repo's importer expects: id, dateStart, dateEnd, pair, rPnL, side, entryPrice, initialSL, maxTP, idealTP, avgRiskReward, tags… | F3 is already built (backend/app/importer.py) |
| Hosting budget | fly.io pay-as-you-go | Aim under $5/month; needs the machine to auto-stop (F2) |
| Ideal trades from FX Replay? | Yes; only winners are imported for ideal trades | Ideal Trades import filters to winners |
| Coverage rule | 6+ trades in total across 6 consecutive months | F9 |
| Privacy between mates | Everything visible by default; strategies can't be duplicated | F12, F15: no copy button |
| Screenshots | FX Replay `/screenshot`, uploaded after the CSV import | U3 (bulk matcher) comes before U4 |
| AI tool for the export | Claude, if needed | Existing export zip is enough; size images for Claude |
| Apify backfill | No | F4: tag only where free history exists |
| Tag vocabulary | One shared list | U5 |
| Breakeven threshold | Anything around 0, out to ±2 | Default threshold 2 (assumed $; say if it's pips) |

- [x] **Push alerts in v1: yes.** Simplest free route: keep one small always-on fly.io machine (roughly $2–4/month, still under the $5 waiver) running an in-app scheduler that sends Web Push to the installed portal on iPhone (iOS 16.4+) and Android before high-impact events. No external cron service needed (F7).

## Sources

All pages opened by the research agents on 5 Nov 2026. GitHub repo pages for the build kit are linked in its table; last-commit dates came from shallow clones because GitHub's API wasn't reachable from this session.

**Hosting, data and feeds**

- [Twelve Data pricing](https://twelvedata.com/pricing) — Basic plan "internal non-display usage"; commodities from Grow
- [Fly.io pricing](https://fly.io/pricing) — trial for new orgs, bills under $5 waived, volumes (Managed Postgres pricing: fly.io/mpg)
- [Tigris pricing](https://www.tigrisdata.com/pricing/) — 5GB free storage, no egress fees
- [JB-News README](https://github.com/jblanked/JB-News) — JBlanked free tier, one request per 5 minutes, per-event history
- [WebKit: Web Push for Web Apps on iOS and iPadOS](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/) — iOS 16.4+, home-screen install required
- [Can I use: View Transitions](https://caniuse.com/view-transitions)

**FX Replay and other journals**

- [FX Replay: Analytics page](https://support.fxreplay.com/articles/analyzing-your-trades-how-to-use-the-fx-replay-analytics-page) · [Metrics defined](https://support.fxreplay.com/articles/analytic-metrics-defined) · [Trades and logging](https://support.fxreplay.com/articles/trades-and-logging) · [FAQs](https://support.fxreplay.com/faqs)
- [TradeZella: Playbook](https://help.tradezella.com/en/articles/7020769-getting-started-with-the-playbook) · [Progress tracker rules](https://help.tradezella.com/en/articles/10371695-understanding-and-using-progress-tracker-rules)
- [Tradervue: MFE and MAE](https://help.tradervue.com/article/3440-mfe-and-mae-calculations)
- [Edgewonk: custom statistics](https://edgewonk.zendesk.com/hc/en-us/articles/360013434820-Custom-Statistics-Settings)

**Claude tools**

- [Claude Code: discover plugins](https://code.claude.com/docs/en/discover-plugins) · [Hooks](https://code.claude.com/docs/en/hooks)
- [flyctl MCP server](https://fly.io/docs/flyctl/mcp-server/) · [Context7 plans](https://context7.vercel.app/plans) · [shadcn MCP](https://ui.shadcn.com/docs/mcp) · [Sentry pricing](https://sentry.io/pricing/)
- Tool repos as linked in the Claude skills and tools table
