# Prompt 3 of 5: Analytics and Export for AI

Paste everything below the line into a fresh `claude` session in `~/Desktop/Trading Portal`.

---

You are building the Trading Portal, Jamie's multi-tool trading web app, in this repo. This is **Prompt 3 of 5: Analytics and Export for AI**. Prompts 1 (Foundations) and 2 (Journal loop) are done; read their reports. Work fully autonomously from start to finish.

## Operating rules (apply all the way through)

- **Don't stop to ask.** If something is undecided, use the Defaults below or the most conservative reasonable choice. Record it under "Assumptions" in the phase report and carry on. Stop early only if continuing would break one of these rules.
- **Read first, in full:**
  - `CLAUDE.md`
  - `docs/planning/trading-portal-foundations.md` (2.4, Charts, Motion → Charts that animate, Devices → Analytics on mobile, Accessibility)
  - `docs/planning/trading-portal-review-and-build-kit.md` (F8, F12, F16, U9, U10, U11)
  - `.claude/skills/trading-portal-tokens/SKILL.md`
  - `docs/build/PROGRESS.md` and every `docs/build/PHASE-*-REPORT.md`

  Jamie's answers to earlier open questions override the Defaults.
- **Resume-safe.** Keep a `## Prompt 3` checklist in `PROGRESS.md`, tick each step and commit. Continue from the first unticked item if it's partly done.
- **Plan, then execute.** Use parallel subagents, for example one to research FX Replay's metric definitions, one to read the old app's analytics and export code, and one to design the chart components. Use Context7 for ECharts 6, echarts-for-react (or a thin wrapper of your own) and TanStack Query.
- **Git.**
  - Start from a clean local `main` and create `build/03-analytics-export` (or resume on it). Make small commits.
  - **Never** push or deploy.
  - Merge into local `main` with `--no-ff` only if the gate passes.
- **Data.**
  - Never read or write `~/ReplayJournal/data`. Dev and test data live under `/tmp/tp-*`.
  - `~/TradingPortal/samples/` is read-only and is never committed.
  - The old app at `~/Desktop/Replay Journal` is reference only.
- **Secrets** never go in the repo. Tests mock every network call.
- **Schema** changes only through Alembic. Permissions are server-side and tested.
- **Design.**
  - Use the tokens skill; charts read colours from CSS variables, never hex.
  - Use the Card pattern, `.num`, reserved colours with +/− signs and icons, 44px targets and WCAG 2.2 AA.
  - Every screen has the five states and is designed for phone, tablet and desktop.
  - Follow the frontend-design skill and the dataviz skill if it's available: at most 2–3 series per chart, thin lines, faint gridlines, real axes and a crosshair.
- **Quality bar.**
  - `make lint` and `make test` pass. Every metric has a pytest test against hand-computed numbers.
  - New screens have Playwright tests at 375px and 1440px, with axe.
  - Run `/check-devices` and the `design-reviewer`, and fix blockers and majors.
  - The bundle budget still passes: ECharts is lazy-loaded and never in the Hub chunk.
- **Don't loop.** If the same failure survives two genuine fixes, log it under "Known issues".

## Defaults

- **Win rate** follows FX Replay's definition, including how it treats breakevens. If their docs are unclear, exclude breakevens from the denominator and say so in the tooltip.
- **Drawdown** is measured peak-to-trough on the cumulative R curve, and on P&L as well.
- **Insights** need at least 8 trades per slice. A slice with n < 20 is labelled "early signal".
- **Monte Carlo** runs 1,000 bootstrap paths of the R sequence in a Web Worker, with a seed so tests are repeatable.
- **AI export images:** long edge ≤ 1568px, which suits Claude's vision input. Use WebP, or JPEG if WebP isn't available.

## Steps

**0. Preflight.** Check the branch, `PROGRESS.md` and the baseline `make test`, `make lint` and `make smoke`. Have a subagent fetch and summarise FX Replay's help pages:
- https://support.fxreplay.com/articles/analytic-metrics-defined
- https://support.fxreplay.com/articles/analyzing-your-trades-how-to-use-the-fx-replay-analytics-page

The summary should give the exact metric list, the formulas and how breakevens are treated. Another subagent reads the old app's analytics and export code.

**1. Metrics engine** (backend, pure functions, F16)
- One **metric registry**. Each metric has an id, label, unit, formula text (shown as a tooltip) and a function.
- Cover FX Replay's set, plus the doc's own:
  - net P&L, win rate, average win, average loss, profit factor
  - expectancy in R and $, average R, total R
  - max drawdown in R and $, longest win and loss streaks
  - best and worst trade, average duration
  - breakdowns by hour, day of week, session, entry model, instrument and direction
  - a daily P&L calendar
- **Reconcile line:** for imported sessions, compare totals with the CSV's own figures (sum of `rPnL`, trade count) and show ✓ or the difference.
- `POST /api/analytics/query` takes:
  - `source` = `ideal` | `backtest` | `compare`
  - `scope` (mine/everyone/others) and `split_by_owner`
  - filters (2.4): date range, instrument, session, entry-time window, day of week, entry model, direction, tags (synonym-aware), outcome (backtest only), owner, rules (all kept / any broken), news (inside/outside, returning "No news data" until Prompt 4 fills it)

  It returns KPIs, series and the registry metadata.
- Performance: 5,000 synthetic trades must come back in under 300ms locally. Add a test that checks this loosely.

**2. Ideal Trades views**
- TP and SL size distributions
- duration distribution
- an entry-time heatmap (hour × weekday)
- entry model breakdown
- day-of-week spread
- the strategy profile summary

**3. Backtest views**
- A KPI strip of 3–5 tiles.
- An equity curve in R: a line with a soft gradient fill underneath, from the accent token.
- Drawdown and streaks.
- Breakdown bars by session, entry model and day of week.
- A P&L calendar (month grid; colour plus a sign, never colour alone).
- An R distribution.
- **Rulebook** (U9): R with all rules kept vs any broken, and each rule's cost in R.
- **Exit efficiency** (U10): realised R ÷ max favourable R, shown when MAE/MFE are present.
- **Monte Carlo:** a percentile band and the probability of a given drawdown, computed in a Web Worker.

**4. Compare view**
- Backtest results set against the ideal profile: how much of the ideal average R is actually captured, and which entry times and models hold up.
- **Split by owner** (F12) uses owner colours. With more than 3 owners, switch to small multiples rather than overlapping lines.

**5. Shared chart system**
- One lazy-loaded `Chart` wrapper over `echarts/core`, tree-shaken.
- A theme built at runtime from CSS tokens.
- Motion:
  - Draw-in on first view: line left to right over about 600ms, bars grow from the baseline, numbers count up.
  - **Morph** on filter change (no flicker).
  - All animation off under reduced motion.
- Hover: a crosshair snapping to the nearest point. Touch: press and hold for the crosshair, tap to pin the tooltip.
- Every chart has a one-line text summary and a "View data table" toggle (Accessibility).
- Chart skeletons while loading.

**6. Analytics layout per device**
- iMac and large screens: filters, chart area and trade list side by side.
- Laptop: filters in a collapsible panel.
- Tablet: filters in a drawer.
- Phone: a 2×2 KPI grid, one full-width chart per row, filters in a bottom sheet, and tables with the first column pinned or switched to cards.
- The Source switch (Ideal · Backtest · Compare) is a PillToggle with a sliding indicator. The filter state lives in the URL, so views can be shared and bookmarked.

**7. Auto-insights** (U11)
- After each import, and on the Analytics tab, a card with the top 3 differences vs the strategy's baseline. For example: "Mondays: SL 30% tighter, n=9 · early signal".
- Plain Python over the query result, with the minimum slice size enforced and no background job.
- Show it on the session recap card too.

**8. Strategy cards.** Swap in the real headline stats: win rate, average R, total R, profit factor, max drawdown and the sparkline.

**9. Export** (F8 plus 2.4)
- **Export for AI** (respects the current filters), streamed as a zip:
  - `trades.jsonl`: one object per trade, with all fields, reasoning, tags, rules, outcome and relative image paths
  - `images/`
  - `strategy.md`: description, rulebook, reasoning template, profile and KPIs, with formulas
  - `README_prompt.md`: a ready-to-paste prompt telling Claude how to analyse the bundle
  - `manifest.json`: app version, export time, filters, counts and per-file SHA-256

  Model it on the old app's export, which Jamie said was enough, and improve it.
- **Copy for AI** puts `strategy.md` plus a compact KPI and trades summary on the clipboard; the icon morphs to a tick.
- **CSV export** of the filtered trades.
- **PDF:** a print stylesheet for the Analytics view, used via "Save as PDF", with no heavy PDF library.
- Tests:
  - the zip structure
  - the manifest hashes
  - JSONL validity
  - image size limits
  - a member can export everyone's data but the export never includes another user's API keys or any secrets

**10. Gate 3 checks** (all must pass)
- For Jamie's real CSV in `~/TradingPortal/samples/` (or the fixture): the Reconcile line is ✓. Write the KPI values into the report so Jamie can compare them against FX Replay's own analytics page.
- Every metric test passes against hand-computed fixtures, including all-wins, all-losses, breakeven-heavy and a single trade.
- Changing a filter morphs the charts, and the URL round-trips the state.
- The AI export unzips cleanly, and its `README_prompt.md` reads well.
- `make lint`, `make test` and `make smoke` are green, and the bundle budget passes.
- `/check-devices` is clean for the Analytics, Compare and Export screens at all six widths. The design-reviewer has no blockers or majors.

## Finish

Write `docs/build/PHASE-3-REPORT.md`:
- What was built
- The gate checklist
- The KPI table for the sample CSV
- Assumptions
- Numbered open questions
- Known issues
- "Jamie's check (10 min)": open the strategy, compare the numbers with FX Replay, export for AI and drop the zip into Claude

Tick `PROGRESS.md`, commit, merge locally if the gate passed, and print a short summary.
