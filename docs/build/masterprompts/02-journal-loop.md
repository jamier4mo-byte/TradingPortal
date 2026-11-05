# Prompt 2 of 5: Replay Journal loop (import, screenshots, annotate)

Paste everything below the line into a fresh `claude` session in `~/Desktop/Trading Portal`. Put your real FX Replay CSV and screenshots in `~/TradingPortal/samples/` first.

---

You are building the Trading Portal, Jamie's multi-tool trading web app, in this repo. This is **Prompt 2 of 5: the Replay Journal loop**. It covers what Jamie does after every FX Replay session: about 10 trades, CSV import, then two screenshots and a reason per trade. Prompt 1 (Foundations) is done; read its report. Work fully autonomously from start to finish.

## Operating rules (apply all the way through)

- **Don't stop to ask.** If something is undecided, use the Defaults below or the most conservative reasonable choice. Record it under "Assumptions" in the phase report and carry on. Stop early only if continuing would break one of these rules.
- **Read first, in full:**
  - `CLAUDE.md`
  - `docs/planning/trading-portal-foundations.md` (sections 2.1–2.4, Motion, Devices)
  - `docs/planning/trading-portal-review-and-build-kit.md`
  - `.claude/skills/trading-portal-tokens/SKILL.md`
  - `docs/build/PROGRESS.md` and every `docs/build/PHASE-*-REPORT.md`

  Answers Jamie gave to earlier open questions are in the reports or in his first message, and they override the Defaults. The Review & Build Kit's **Decisions** and **F1–F19** override the Foundations doc.
- **Resume-safe.** Keep a `## Prompt 2` checklist in `docs/build/PROGRESS.md`. Tick each step when it lands and commit. If it's partly done, continue from the first unticked item.
- **Plan, then execute.** Turn the steps into a task list. Use the Explore and Plan subagents in parallel, for example one to read the old importer and exporter and one to design the matcher. Use Context7 for current APIs.
- **Git.**
  - Start from a clean local `main` and create `build/02-journal-loop` (or resume on it). Make small commits.
  - **Never** push, deploy or touch Fly.
  - At the end, if the gate passes, merge into local `main` with `--no-ff`. Otherwise leave it unmerged and explain why.
- **Data.**
  - Never read or write `~/ReplayJournal/data`. Dev and test data live under `/tmp/tp-*`.
  - `~/TradingPortal/samples/` holds Jamie's real files. **Read them only**, and never commit them or copy them into the repo. Test fixtures are synthetic, built to match the real header and quirks.
  - `~/Desktop/Replay Journal` is reference only: never edit it or copy it wholesale.
- **Secrets** never go in the repo. Tests mock every network call.
- **Database.**
  - Schema changes only through Alembic migrations.
  - Every owned record has `owner_id`, timestamps and `deleted_at`.
  - Permissions are checked server-side and tested: members change only their own; the admin changes anything.
- **Design.**
  - Use the tokens skill, with no hex outside `@theme`. Use the Card pattern, `.num` and reserved colours (with +/− signs and icons, never colour alone), 44px targets and WCAG 2.2 AA.
  - Every screen has the five states (skeleton, empty, error, read-only, offline) and is designed for phone, tablet and desktop. Reuse the Prompt 1 components.
  - Follow the frontend-design skill.
- **Quality bar for every step.**
  - `make lint` and `make test` pass. New logic has pytest tests; new screens have Playwright e2e tests at 375px and 1440px, with axe.
  - After UI work, run `/check-devices` and the `design-reviewer` subagent, and fix blockers and majors.
- **Don't loop.** If the same failure survives two genuine fixes, log it under "Known issues" and move on.

## Defaults

- **Breakeven:** |P&L| ≤ the user's threshold (default 2, account currency).
  - Win means above it; loss means below the negative threshold.
  - Ideal import keeps **winners only**.
- **Coverage and unlock** (F9 plus Jamie's decision): one function and one set of constants everywhere.
  - A month is covered when it holds at least 1 non-deleted ideal trade, by the trade's open date in UK time (Europe/London).
  - Unlock needs 6 consecutive covered months, which also means 6+ trades.
  - Keep the threshold constants in one module so the rule can be changed in one place.
- **Duplicate key:** (strategy, FX Replay trade `id`). A re-import skips duplicates and reports them.
- **Screenshots** (F10): an Entry slot, an Exit slot and up to 3 extras.
  - The browser converts each to WebP: about 1920px long edge for the full image (about 250KB), plus a 400px thumbnail.
  - Served only through authenticated endpoints, never public static.
- **Storage:** a `Storage` interface with `LocalStorage` under the data directory now. The S3/Tigris version comes in Prompt 5.
- There is no "duplicate strategy" action anywhere.

## Steps

**0. Preflight**
- Check the branch, `git status` and the `PROGRESS.md` section.
- Run `make test`, `make lint` and `make smoke` for a baseline.
- Have a subagent read the old app's `backend/app/importer.py` (and its exporter, analytics and screenshot code, if present) under `~/Desktop/Replay Journal`. It should summarise the FX Replay column meanings, timezone handling and edge cases.
- List `~/TradingPortal/samples/` and note the CSV header and screenshot filenames, without printing trade values.

**1. Data model** (one migration set)
- `strategies`
  - owner, name, instruments, timeframes, description, entry models
  - CSV timezone: default `Europe/London`, `UTC` allowed
  - a rulebook of 4–8 rules (U9)
  - a structured reasoning template (U5): default fields HTF bias, draw on liquidity, PD array / entry model, killzone, confluences, invalidation
  - computed stage: Ideal Trades → Ready to backtest → Backtesting
- `sessions` (U1)
  - strategy, owner, kind (`ideal`, `backtest` or `manual`), CSV timezone, replayed date range, trade count
  - source filename and file hash
  - an "one thing to improve" note
  - undone-at
- `trades`
  - strategy, session and owner
  - kind: `ideal`, `backtest` or `missed` (U13)
  - FX Replay id, instrument, side
  - open and close time (stored in UTC), market date, session label (Asia/London/NY, from UK session times), duration
  - entry, SL and TP (`initialSL`, `maxTP`, `idealTP`), SL and TP distance in pips/points and as R
  - R multiple, P&L, outcome
  - entry model, tags (many-to-many with the tag vocabulary, via `resolve_tag`)
  - reasoning (JSON keyed by template field), notes
  - rules followed (JSON keyed by rule)
  - optional MAE and MFE (U10)
  - news fields left null for Prompt 4
  - the raw CSV row as JSON
- `screenshots`: trade, slot, storage keys for the full image and thumbnail, width and height, bytes, capture time, original filename.
- A pip/point size per instrument, in one table, editable by the admin. Seed it with the FX majors, XAUUSD, BTCUSD, GER40 and NAS100.

**2. FX Replay CSV importer** (F3: build this first)
- Parse the real export format: the 22 columns `id, dateStart, dateEnd, pair, rPnL, side, entryPrice, initialSL, maxTP, idealTP, avgRiskReward, tags…`. Confirm them against the sample in `~/TradingPortal/samples/` and the old importer. Handle BOM, quoting, date formats, empty cells and FX Replay's tag separator.
- **Flow:** upload → **preview** → confirm → Session created.
  - The preview shows rows parsed, detected date range, timezone used, duplicates, winners/losers/breakevens, and exactly what each destination would import.
  - The destination switch is **Ideal (winners only)** or **Backtest (all)**.
- **Undo a whole session.** It soft-deletes that session's trades, and a toast offers Undo.
- **Progress UI** with stages: Reading file → Matching trades → Calculating stats → Done, ending with "10 trades imported".
- Write a synthetic fixture CSV that mirrors the real header. Tests cover:
  - timezone conversion, including a DST boundary
  - duplicates
  - breakeven classification at ±2
  - a winners-only ideal import
  - undo
  - malformed rows, which are reported, not crashed on

**3. Screenshots and the bulk matcher** (U3: the Must that comes before Annotate mode)
- Upload API: type checked by magic bytes, size limits, and a path-safe storage key. It creates the full image and thumbnail.
- Browser pipeline: paste, drag-and-drop or file picker → WebP full + thumbnail, made in the browser (OffscreenCanvas or canvas). Each thumbnail fills as it uploads.
- **Bulk matcher:** drop all the images at once, for example 20. Pair them by:
  1. **Filename:** patterns like `T03_entry.png`, `t3-exit`, `3e/3x`, `trade 3 entry`
  2. **Capture time:** EXIF, the macOS `Screenshot YYYY-MM-DD at HH.MM.SS` name, or the file's last-modified time. Match against trade open and close times in the strategy's timezone.
- Show a trades × (Entry, Exit) grid with confidence badges, plus an "Unmatched" tray. Drag to fix, then **Save all**.
- Phone: multi-select from Photos, matched by capture time, shown as a list rather than a grid.
- Unit-test the matching logic with synthetic names and times.

**4. Annotate mode** (U4)
- A full-screen stepper ("Trade 3/10") across a session's trades.
- **Cmd+V** fills Entry, then Exit, then focuses Reason, then moves to the next trade. **J/K** go next/previous, and Esc exits.
- Each trade shows:
  - the reasoning template fields
  - the rulebook checklist
  - tags with synonym-aware autocomplete
  - optional MAE/MFE
  - an "Autosaved" indicator
- Phone: camera-roll pickers and large controls.
- The **session inbox** on the strategy page (U1) shows "10 trades · 14/20 screenshots · 6/10 reasons" with a **Finish annotating** button.

**5. Strategy screens** (2.1–2.3)
- **Overview grid.** Each strategy card shows:
  - name, creator (OwnerChip) and stage chip
  - ideal-trade count and date range
  - a coverage progress bar towards 6 months
  - basic backtest headline stats once available (win rate, total R, average R; the full set comes in Prompt 3)
  - last updated
  - an R sparkline

  Plus a "+ New strategy" form. The ViewScopeToggle defaults to Everyone, and phones get a single column.
- **Strategy page** with tabs: Ideal Trades · Backtest · Analytics (a placeholder until Prompt 3), as a segmented control on the phone.
- **Ideal Trades tab:**
  - trade list (a table on desktop, cards on the phone)
  - a quick-log drawer that remembers recent values and pre-fills strategy defaults, with screenshot slots, paste and drag
  - a missing-screenshot badge
  - a coverage tracker: a months grid showing 6-month progress and the trade count
  - a trade detail view with a swipeable, pinch-to-zoom gallery, loading the thumbnail first and full resolution on zoom
- **Strategy profile** (2.2): computed once the strategy unlocks, and cached until the trades change. It shows:
  - average TP and SL distance, average R and typical duration
  - most common entry times and sessions
  - entry model frequency and day-of-week spread
  - the most common tags and confluences
- **Backtest tab:**
  - Locked, showing coverage progress, until it unlocks. An **Open early** button opens it with a warning.
  - The strategy profile sits at the top as the reference rules.
  - A trade list with outcome chips (+/− icons), R, P&L and rules followed.
  - Manual entry, and CSV import with the Backtest destination.
- **Session recap card** after an import: trades, win rate, total R, rules followed and the best trade's screenshot. It animates in using the motion tokens.
- **Pre-session brief** (U7): "Start session" opens the strategy profile, the rule checklist, the last 2 sessions' "one thing to improve" and the next uncovered month to replay. Leave a slot for news, which Prompt 4 fills.
- **Missed setups** (U13): log "Saw it, didn't take it" with one screenshot and a reason. These stay out of P&L.
- **Trash** (F5): deleted strategies, trades and sessions can be restored for 30 days. The purge job comes in Prompt 5.
- The Hub's ReplayJournal island will need a "last session" mini-stat, so expose `GET /api/journal/summary` now.

**6. Gate 2 checks** (all must pass)
- Using the real CSV from `~/TradingPortal/samples/` (or the fixture if that's empty, and say so):
  - Import it into a test strategy as Ideal: winners only, the right count, and times correct in UK time.
  - Import it again as Backtest: all trades.
  - A third import reports every row as a duplicate.
  - Undo removes a session and its Undo restores it.
- Dropping the real screenshots (or 16 synthetic ones) matches at least 90% automatically, and the rest can be fixed in the grid.
- Keyboard only (Playwright): Annotate mode completes 8 trades with paste-in screenshots and reasons.
- Coverage and unlock unit tests pass: a gap month, a year boundary, a trade near midnight UK time, deleted trades not counting, and exactly 6 consecutive months.
- A member gets 403 on the admin's strategy and trades and sees the read-only banner.
- `make lint`, `make test` and `make smoke` are green. `/check-devices` is clean at all six widths for the journal screens, Annotate mode and the matcher. The design-reviewer has no blockers or majors.

## Finish

Write `docs/build/PHASE-2-REPORT.md` with the same sections as Phase 1:
- What was built
- The gate checklist with how each item was verified
- Assumptions
- Open questions for Jamie, numbered, answerable in one line each
- Known issues
- "Jamie's check (15 min)": the exact steps to import his own CSV and screenshots through the UI on `make dev`

Tick `PROGRESS.md`, commit, merge locally if the gate passed, and print a short summary.
