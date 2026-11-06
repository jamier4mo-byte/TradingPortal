# Phase 3 report: Analytics and Export for AI

Branch `build/03-analytics-export`, 6 Nov 2026. Gate 3: see the checklist below.

## What was built

**Metrics engine** (`backend/app/services/analytics/`, pure Python over flat rows, F16)
- `metrics.py`: one registry of 36 metrics. Each has an id, label, unit, the formula text the UI shows, and a function. It covers FX Replay's set (win rate with breakevens left out, net P&L, average and max RR on winners, profit factor, best and worst, average duration split by wins and losses, max consecutive, winner drawdown from MAE) and the doc's own (expectancy in R and $, average R, total R, max drawdown in R and $ on the cumulative curve, rules-kept rate, exit efficiency, R left on the table, the ideal-profile sizes and the typical duration).
- `series.py`:
  - breakdowns by hour, weekday, session, entry model, instrument and direction
  - the equity and drawdown series, streak runs, the daily P&L calendar (UK open date), the R histogram and the hour × weekday heatmap
  - the ideal distributions: TP in R, TP and SL size, and duration buckets
  - the rulebook (all kept vs any broken, and each rule's cost in R)
  - excursions, Compare (capture, and what holds up by hour, model, session and day), and the owner split
- `insights.py` (U11): the top 3 slice-vs-baseline differences. A slice needs 8 trades; under 20 it's labelled "early signal". It is plain Python, computed on request with no background job. Insights always compare with the strategy's unfiltered baseline.
- `reconcile.py`: each import now stores FX Replay's own figures (row count, Σ rPnL, first `initialBalance` and last `currentRealizedBalance`) and what the import kept. The Reconcile line compares them with the live trades and explains any difference (winners only for Ideal, duplicates, trades deleted since).
- `query.py`: `POST /api/analytics/query`. It takes `source` (ideal, backtest or compare), `scope`, `split_by_owner` and every 2.4 filter:
  - date range, instrument, session, an entry-time window that wraps midnight, and weekday
  - entry model, direction, tags (synonym-aware), outcome (backtest only) and owner
  - rules (all kept / any broken), and news (no data yet: the filter is accepted, not applied, and the answer says "No news data")

  Rows are loaded with one column select plus one tag select: **5,000 trades take 144 ms**.
- `export.py`: Export for AI as a **streamed zip** (`GET /api/analytics/export/ai?q=…`) containing:
  - `trades.jsonl`
  - `images/`, long edge ≤ 1,568 px, WebP
  - `strategy.md`, with KPIs and their formulas, breakdown tables, rulebook adherence, insights and the reconcile line
  - `README_prompt.md`
  - `manifest.json`, with app version, time, filters, counts and a SHA-256 for every file

  Alongside it: **Copy for AI** (`POST /api/analytics/copy`) and a **CSV** of the filtered trades. CSV cells that start like a formula are neutralised.
- Strategy cards and session stats now come from the same engine: win rate, average R, total R, profit factor, max drawdown and trades, using the viewer's breakeven threshold. `GET /api/journal/sessions/{id}/insights` feeds the recap card.
- Hardening:
  - A non-finite number (`inf` in a CSV, `Infinity` in JSON) is refused on write, treated as missing on load, and can't stall the histogram.
  - A 422 response no longer crashes when the input was Infinity.
- `make seed-dev` adds three synthetic strategies (Jamie 35 ideal + 160 backtest, Sam 80, Alex 40) so every screen has data. These are dev data only, under `/tmp`.

**Front end**
- `components/charts/`:
  - one `Chart` wrapper over a tree-shaken `echarts/core`, loaded lazily (its own 201 KB gzip chunk, never in the Hub's chunk)
  - a theme built at runtime from the CSS tokens
  - charts start when they scroll near the view, so lines draw left to right and bars grow from the baseline on first sight
  - later data merges into the same series, so charts morph on a filter change while the old frame dims instead of flickering
  - animation is off under Reduced or Off motion
  - crosshair and axis tooltips (escaped). On touch, press and drag moves the crosshair and a tap pins the tooltip
  - every chart has a one-line summary and a "View data table" toggle
  - charts redraw with light print tokens for Save as PDF
- `pages/journal/analytics/`:
  - **Backtest**: a KPI strip that counts up and shows its formula on tap; the equity curve in R or $ with a soft accent fill and an end label; drawdown and win/loss runs; the R distribution; breakdowns (session, model, day, hour, side × total R, win %, avg R); the P&L calendar (a month grid with signs as well as colour, and week totals on laptop); the rulebook with each rule's cost; exit efficiency with an R vs MFE scatter; Monte Carlo (1,000 seeded bootstrap paths in a Web Worker, percentile bands, and the chance of a drawdown of at least X R); and every metric with its formula.
  - **Ideal**: TP/SL sizes, duration, the entry-time heatmap, entry models, day of week and the strategy profile.
  - **Compare**: winners capture and per-trade capture, average R and stop compared, and a "What holds up" table by hour, model, session or day with Holds / Fails / Too few.
  - **Split by owner** (F12): owner-coloured lines with a legend and end labels for up to 3 owners; small multiples above 3.
  - Auto-insights card, the Reconcile line, and the trade list.
  - The five states: skeletons, the "No backtest trades yet" and "No trades match these filters" empty states, error with retry, the read-only banner from the strategy page, and the shell's offline banner.
- Layout per device:
  - ≥ 1920: filters | charts | trades side by side
  - 1440–1919: filters at the side
  - laptop: a collapsible filter panel
  - tablet: a drawer
  - phone: a bottom sheet with "Show N trades", a 2×2 KPI grid, one chart per row, and the compare table scrolling sideways with its first column pinned
- The Source switch is the shared PillToggle with a sliding indicator. **Source, scope, split and every filter live in the URL.**
- `/journal/analytics`: every strategy together (Mine · Everyone · Others, split by owner), linked from the strategy grid.
- The Export drawer (`?export=1`) has the zip, Copy for AI (the icon morphs to a tick), CSV, and Save as PDF (a print stylesheet; no PDF library).
- The session recap gains "How it compares". Strategy cards show six real headline stats.
- `make test` now also runs the front end's Node unit tests (`node --test`, Monte Carlo). The bundle check fails if ECharts ever reaches the Hub.

**Tests**: 260 pytest (49 new), 6 Node unit tests (`make test` runs both), and 110 Playwright tests at 1440 and 375 px with axe (`e2e/analytics.spec.ts` adds 18 checks per width).

## Gate 3 checklist

| Check | Result | How verified |
|---|---|---|
| Real CSV: the Reconcile line is ✓ and the KPIs are written down | Pass | `Samples/02:11:26 Backtest x8 Trades.csv` imported as Backtest into a throwaway `/tmp/tp-gate3`: CSV 8 rows · Σ rPnL $5,475.76 = app 8 trades · $5,475.76; FX Replay's balance change ($1,000 → $6,475.76) matches. KPI table below. Also `test_real_sample_reconciles` (skips where the file isn't present) |
| Every metric test passes on hand-computed fixtures (mixed, all wins, all losses, breakeven-heavy, single trade, none) | Pass | `tests/test_metrics.py` (19): every registry metric against the worked numbers in its docstring, plus breakdowns, calendar, equity, drawdown, streaks, histogram, rulebook costs, Compare capture, insights (8-trade minimum, "early signal" under 20). `test_analytics_api.py` (19): every filter, scope, split, permissions, threshold, insights baseline, 5,000 trades in 144 ms. Monte Carlo: 6 seeded Node tests |
| Changing a filter morphs the charts; the URL round-trips the state | Pass | Charts merge new data into the same series ids (ECharts `replaceMerge`), with the previous frame dimmed while it loads (TanStack `keepPreviousData`). Checked by hand: Mon → 33 of 160 trades, the curve bends in place. e2e "a filter lands in the URL, narrows every number, and survives a reload" (both widths) and "the source switch keeps its place in the URL" |
| The AI export unzips cleanly and `README_prompt.md` reads well | Pass | The real CSV's export: `testzip()` clean; README, strategy.md, trades.jsonl and manifest read through by hand (fixed on the way: pipes in formulas broke the Markdown table; R values had 15 decimals; "0 screenshots" now says none were added). `tests/test_export.py` (11): layout, manifest SHA-256s, JSONL fields, images ≤ 1,568 px WebP, filters respected, no secrets or emails even when a member exports everyone's data, CSV formula neutralising, Copy for AI |
| `make lint`, `make test`, `make smoke` green; bundle budget | Pass | lint clean (ruff, oxlint, tsc, bundle **185.1 KB** of 200; ECharts is a lazy 201 KB chunk and the check now fails if it ever reaches the Hub); 260 pytest + 6 Node; **110 Playwright** |
| `/check-devices` clean for Analytics, Compare and Export at all six widths; design-reviewer has no blockers or majors | Pass | `docs/check-devices/2026-11-06-p3/` (36 screenshots: analytics, ideal, compare, export, all-strategies, journal × 360/375/430/768/1440/1920; not committed). Fixed on the way: the strategy grid header overflowed the phone by 26 px (it wraps now), and owner-line end labels collided. design-reviewer pass 1: 0 blockers, 4 majors (print contrast and blank lazy charts in Save as PDF, hard-coded motion timings, no offline state), all fixed with most minors and nits; pass 2: all four resolved, **no new blockers or majors ("ship")**; three of its new minors fixed (the afterprint redraw keeps motion and touch, an offline first load shows an offline state, CountUp no longer writes the final number before counting) |

## KPIs for the sample CSV (`Samples/02:11:26 Backtest x8 Trades.csv`, imported as Backtest)

Compare these with FX Replay's own Analytics page for the same session.

| Metric | Trading Portal | From FX Replay's CSV |
|---|---|---|
| Trades | 8 (8 wins, 0 losses, 0 breakevens) | 8 rows |
| Net P&L | +$5,475.76 | Σ rPnL $5,475.76; balance $1,000 → $6,475.76 (+547.6%) |
| Win rate | 100% | |
| Total R | +34.09R | Σ avgRiskReward 34.10 |
| Average R (= Average RR on winners) | +4.26R | mean avgRiskReward 4.2625 (rounded per row in the CSV) |
| Expectancy | +4.26R · +$684.47 | |
| Profit factor | — (no losses: undefined) | |
| Max drawdown | 0.00R · $0.00 | |
| Longest win / loss streak | 8 / 0 | |
| Best / worst trade | +5.23R ($885.30) / +3.12R ($520.05) | maxRiskReward column is per trade; best avgRiskReward 5.23 |
| Average duration | 1d 16h (144,598 s) | |
| Average stop | 108.9 points | |
| Exit efficiency | 52% of the best R available | from FX Replay's idealTP (best price) |
| R left on the table | +3.88R per trade | |
| Reconcile | ✓ 8 trades · +$5,475.76 = 8 rows · Σ rPnL $5,475.76; balance check ✓ | |

## Assumptions
1. **Win rate** follows FX Replay's help page: wins ÷ (wins + losses), with breakevens left out. The tooltip says so.
2. **Breakeven** stays Jamie's ±$2 on P&L (settled 5 Nov), not FX Replay's R-based threshold. It is recomputed at query time with the viewer's own setting, so changing the setting updates every number.
3. **P&L is booked at close** for the equity curve, drawdown and streaks, as FX Replay and the old app do. The calendar, weekday and hour views use the **open** time in UK time.
4. **Drawdown** is peak-to-trough on cumulative R and cumulative P&L, starting from 0, and shown as a negative number. FX Replay's own "Drawdown" tab is something else: how far price went against a winner. That's here as "Winner drawdown" when MAE is entered.
5. **Expectancy** = win rate × average win − (1 − win rate) × |average loss|, using the same win rate (breakevens left out). **Average R** is total R ÷ trades, breakevens included. FX Replay shows expectancy as a bar with no formula.
6. **Profit factor** = gross $ of wins ÷ gross $ of losses. With no losses it is undefined (shown "—"), never ∞. An R version is also in the registry.
7. **A breakeven ends a streak**, as in the old app. FX Replay's docs don't say.
8. **Exit efficiency** = Σ max(R, 0) ÷ Σ best favourable R, over trades with an excursion. The best R comes from the MFE typed in Annotate mode, or else from FX Replay's `idealTP`. FX Replay defines that as the best price up to a week after the close, so imported trades can look less efficient than a strict in-trade MFE would.
9. **Rule cost** = trades that broke the rule × (average R when kept − average R when broken).
10. **Insights** compare each slice with the strategy's unfiltered baseline. They look at stop size, target R, duration, and (for backtests) win rate and average R. A difference needs to be 15% or more. One insight per slice; ranked by effect × √n.
11. **Monte Carlo**: 1,000 bootstrap paths of the R sequence, each as long as the history, with seed 20261106. The default drawdown question is 5R and you can change it.
12. **News filter**: there's no news data until Prompt 4, so the filter is accepted but not applied, and the screen says "No news data".
13. **Exports are GET downloads** with the query as JSON in `q`, so the browser streams the zip straight to disk. Filters aren't personal data. A member can export everyone's trades, but the export reads only trade, strategy and display-name data: no emails, password hashes, sessions or keys. A test proves it.
14. **AI images** are re-encoded WebP (quality 85) at most 1,568 px on the long edge, from the stored full-size WebP.
15. Exports and Copy for AI follow the current source and filters. Copy for AI lists at most 120 trades and points to the zip for the rest.
16. **Split by owner** sits on the all-strategies page and on any strategy with more than one owner. Inside a single strategy all trades usually share the owner (Phase 2 assumption 3).
17. The strategy card's numbers use the viewer's breakeven threshold.

## Open questions for Jamie
1. Breakeven: FX Replay measures it in R (e.g. ±0.1R), we use ±$2. Keep $, switch to R, or offer both in Settings?
2. Exit efficiency on imported trades uses FX Replay's "ideal" price, which can be up to a week after the close. Count that as the best available, or only use MFE you type in?
3. Is "a breakeven ends a streak" how you read FX Replay's Max consecutive?
4. The Monte Carlo question defaults to "a 5R drawdown". Is there a figure you'd rather see by default (your daily or total loss limit in R)?
5. The owner colours and the second chart series pass colour-blind separation and contrast but sit lighter than the dataviz validator's preferred band on dark, and sand reads a little grey. Keep them, or try darker steps?
6. Should Copy for AI include the screenshots' file names, or stay text only?
7. The phone hides Expectancy from the 2×2 KPI grid; it's still in "Every metric". Want a different four?

## Known issues
- **Save as PDF** was checked in code and through the print tokens, not by printing from Safari and Chrome. Whether background colours print depends on the browser's "Background graphics" option. Pressing ⌘P directly (rather than Export → Save as PDF) prints only the charts that have already scrolled into view.
- The ECharts chunk is 201 KB gzip. It's lazy and never on the Hub, but it's the heaviest download on the Analytics tab. An SVG renderer or fewer components could trim it in Prompt 5.
- Design-review minors left open: the print wait (`+900 ms`) and heatmap stagger (30 ms) are timings outside `@theme`; the Drawer description and Card subtitles are plain strings, so "160 trades" and "1,000" in them aren't `.num`; the 5-tile KPI strip leaves a gap on tablet (3 + 2).
- Insights on the tiny Samples CSV: none (8 trades, all winners, no 8-trade slice that differs from the rest). They appear on larger sets, such as the dev seed.
- The FX Replay "ideal" price is used as MFE for imported trades (Assumption 8; Open question 2).
- Context7 still rejects calls, so ECharts 6 and TanStack Query APIs were read from the installed packages.
- The local preview server needed `python -m uvicorn`: the venv's `uvicorn` launcher script has a stale interpreter path. `make dev` and `make run` call `.venv/bin/uvicorn` and may need `make setup-backend` to refresh the venv.

## Jamie's check (10 min)
1. `make dev`, sign in, open your NAS100 strategy (or import `Samples/02:11:26 Backtest x8 Trades.csv` as **Backtest** into a new one) → **Analytics** tab.
2. Check the Reconcile line under the toolbar: "Reconciled with FX Replay ✓ · 8 trades · +$5,475.76". Open **Details** for the CSV vs app figures.
3. Open FX Replay's Analytics page for the same session and compare: Total PnL $5,475.76, Win rate 100%, Average RR 4.26, Max RR 5.23, Breakeven trades 0. Tap the ⓘ on any KPI tile for its formula. "Every metric" at the bottom lists them all.
4. Click **Mon**, then **Short**, in the filters (the Filters button on a laptop, tablet or phone): the charts reshape and the URL changes. Copy the URL into a new tab and it opens the same view. **Clear all**.
5. Switch **Ideal** → **Compare** → **Backtest** with the pill at the top.
6. **Export** → **Download zip for AI**. Unzip it and read `README_prompt.md`. Then drop the zip (or `README_prompt.md` plus the other files) into Claude and say "Go".
7. **Copy for AI**, then paste into a Claude chat: the dossier and a compact trade table.
8. **Export** → **Save as PDF**: the print dialog shows a light, chrome-free page.
9. On the phone (or a 375 px window): 2×2 KPI tiles, Filters in a bottom sheet, one chart per row. Press and drag on the equity curve for the crosshair; tap to pin the tooltip.
10. `/journal/analytics?split=1` (Analytics on the strategy grid) → Split by owner shows everyone's curves in their owner colours.
