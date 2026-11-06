# Phase 2 report: the Replay Journal loop

Branch `build/02-journal-loop`, 6 Nov 2026. Gate 2: see the checklist below.

## What was built

**Backend** (`backend/app/`)
- Migration `0004_journal`: `instruments` (seeded with the FX majors, XAUUSD, BTCUSD, GER40, NAS100 with pip/point sizes and FX Replay aliases), `strategies`, `journal_sessions`, `trades`, `trade_tags`, `screenshots`. Every owned table has `owner_id`, `created_at`, `updated_at`, `deleted_at`. Trades are unique on (strategy, kind, FX Replay id).
- `services/journal_rules.py`: the rules in one module. `COVERAGE_MONTHS = 6`, `MIN_UNLOCK_TRADES = 6`, `DEFAULT_BREAKEVEN_THRESHOLD = 2.0`, UK session windows (Asia 00–08, London 08–13, New York 13–22), `classify_outcome`, `market_date` (UK), `session_label`, `coverage()` (months grid with gaps, best run, next month to replay) and `stage()`.
- `services/fxreplay.py`: the CSV parser. Looks columns up by name (the real 22-column header: `id,dateStart,dateEnd,pair,uPnL,rPnL,side,entryPrice,initialSL,maxTP,idealTP,amount,amountClosed,status,day,tags,avgClosePrice,avgRiskReward,maxRiskReward,exchangeRate,initialBalance,currentRealizedBalance`), handles BOM, CRLF, quoting, thousands commas, seven date formats, empty cells, `;`/`,`/`|` tag separators and the strategy's chart timezone (`Europe/London` default, `UTC` allowed) with proper DST conversion to UTC. Bad rows are reported as `line N: reason`, never fatal. Realised R is direction × (close − entry) ÷ |entry − SL| and matches FX Replay's `avgRiskReward` to within 0.005 on the fixture.
- `services/instruments.py`: `OANDA:NAS100USD` → `NAS100`, pip size and unit per instrument, FX heuristic fallback.
- `services/journal.py`: strategies (rulebook 4–8, reasoning template), trades (quick log, backtest manual entry, missed setups out of P&L, tags through `resolve_tag`, SL/TP distances in pips/points and as R), imports (preview → confirm → Session; Ideal keeps winners only; Backtest keeps all; duplicates skipped and reported per destination), undo and restore of a whole session, Trash (30 days), session progress ("10 trades · 14/20 screenshots · 6/10 reasons"), headline stats, R sparkline, the strategy profile (computed once unlocked or opened early, cached on the strategy row until the trades change), and the Hub summary.
- `services/storage.py`: a `Storage` interface and `LocalStorage` under `<data dir>/screenshots` with path-safe keys. S3/Tigris comes in Prompt 5.
- `services/screenshots.py`: magic-byte type check (PNG, JPEG, WebP, GIF), 12 MB cap, dimension cap before decoding (decompression-bomb guard), Entry/Exit slots plus up to 3 extras, server-made WebP thumbnail when the browser didn't send one, move (swap) and delete.
- `services/matcher.py`: the bulk matcher. Pass 1 filenames (`T03_entry`, `t3-exit`, `3e`/`3x`, `trade 3 entry`, `entry_t3`…), pass 2 capture time (EXIF, the macOS `Screenshot YYYY-MM-DD at HH.MM.SS` name, or last-modified) against open/close times in the strategy's timezone within 90 minutes, pass 3 sequence into the empty slots at low confidence.
- `api/journal.py`: `/api/instruments`, `/api/strategies[...]` (list with `?scope=`, CRUD, restore, `/profile`, `/brief`, `/trades`, `/imports/preview`, `/imports`, `/sessions`), `/api/trades/{id}` (get, patch, delete, restore, `/screenshots`), `/api/journal/sessions/{id}` (get, trades, patch note, undo, restore, `/match`), `/api/screenshots/{id}/full|thumb` (authenticated only, never static), `/api/journal/trash`, `/api/journal/summary`.
- `make seed-dev` now also creates two strategies with the fixture imported, so the journal screens have data.
- 208 pytest tests (72 new): parser, rules, matcher, API, permissions, screenshots.

**Front end** (`frontend/src/`)
- `lib/journal.ts` (types, queries, formatters) and `lib/images.ts` (browser pipeline: any image → WebP ~1920px full plus 400px thumbnail via OffscreenCanvas, EXIF `DateTimeOriginal` reader for JPEG and PNG, macOS screenshot name parser).
- `/journal`: strategy grid (name, OwnerChip, stage chip, ideal count and date range, six-block coverage bar, backtest headline stats, last updated, R sparkline), ViewScopeToggle defaulting to Everyone, "+ New strategy" drawer, single column on the phone, Trash link. The phone "+" opens a strategy picker that lands on the quick log.
- `/journal/strategies/:id`: header with actions (Start session, Import CSV, Log trade, edit, delete), read-only banner for other people's strategies, session inbox (progress, Recap, Match screenshots, Finish annotating, Undo), tabs Ideal trades · Backtest · Analytics (segmented control). Ideal tab: coverage months grid, trade list (table on desktop, cards on the phone, missing-screenshot badge), missed setups. Backtest tab: locked state with ring gauge and Open early (with a warning), strategy profile at the top, rulebook, trade list with outcome chips (+/− icons), R, P&L and rules followed, manual entry and CSV import with the Backtest destination. Analytics tab: placeholder with the live headline numbers.
- Import drawer: file picker or drop → preview (rows parsed, date range, timezone, winners/losers/breakevens, duplicates per destination, unreadable rows, and a row table saying exactly what imports) → Ideal/Backtest switch → progress stages Reading file → Matching trades → Calculating stats → Done → "N trades imported" with Undo in the toast (and Undo of the undo) → Add the screenshots / Annotate trades.
- Quick log drawer: strategy defaults and recent values remembered, Ideal/Backtest/Missed switch, native number and datetime inputs, entry-model datalist, synonym-aware tag autocomplete, then Entry/Exit screenshot slots (paste, drop, picker or camera roll).
- `/journal/sessions/:sid/match`: drop everything at once; thumbnails fill as they're read; the grid of trades × (Entry, Exit) with Sure/Likely/Guess badges and an Unmatched tray; tap-to-pick or drag to fix; Save all uploads two at a time and lands in Annotate mode. The phone gets a list and multi-select from Photos.
- `/journal/sessions/:sid/annotate`: full-screen "Trade 3/10" stepper. ⌘V fills Entry, then Exit, then focuses the first reason field; Enter steps through the template and the last Enter moves to the next trade; J/K previous/next; ⌘↵ next; Esc exits. Reasoning template, rulebook checklist, tags, MAE/MFE, notes, "Autosaved" indicator, progress dots. Phone: stacked, camera-roll pickers, big controls.
- `/journal/strategies/:id/trades/:tid`: detail with a swipeable gallery (scroll-snap), full-screen viewer (thumbnail first, full resolution on zoom; pinch, wheel, double-tap and +/− keys), facts, tags, reasoning, rules followed, Annotate and Delete.
- `/journal/trash`: strategies, sessions and trades with Restore.
- Hub: the Replay Journal island shows "Last session: 10 trades · 2 h ago" from `GET /api/journal/summary`.
- 30 new Playwright tests (76 total) at 1440 and 375 with axe; the suite passed three times in a row.

## Gate 2 checklist

| Check | Result | How verified |
|---|---|---|
| Real CSV (`Samples/02:11:26 Backtest x8 Trades.csv`, 8 trades, Feb 2026): Ideal import keeps winners only with the right count and UK times | Pass | API run against a throwaway data dir: 8 of 8 rows parsed, no problems, all 8 are winners, 8 imported as ideal; stored UTC equals the CSV clock (February is GMT) and sessions label Asia/New York/Out of session correctly. Backend `test_ideal_import_keeps_winners_only` covers BST and the DST boundaries on the synthetic fixture |
| Import it again as Backtest: all trades | Pass | Same run: 8 of 8 imported into the backtest ledger (the duplicate key is per destination, see Assumptions) |
| A third import reports every row as a duplicate | Pass | Same run: 0 imported, 8 duplicates reported; e2e "import flow" shows "10 trades are already in this strategy's backtest" and a disabled Import button |
| Undo removes a session and its Undo restores it | Pass | Same run (8 removed, 8 restored); backend `test_undo_session_soft_deletes…`; e2e "import flow" uses the toast Undo and its Undo |
| Dropping the screenshots matches ≥ 90% automatically, rest fixable in the grid | Pass with 16 synthetic names (16/16 "Sure"); see Known issues for the real files | e2e "bulk matcher pairs 16 dropped files" (both viewports), plus a tap-to-move and move-back; `test_matcher.py` (11 tests). The real 21 files have hash names and download-time mtimes, so they land by sequence (16 placed at "Guess", 5 to the tray) and need a check in the grid |
| Keyboard only: Annotate mode completes 8 trades with paste-in screenshots and reasons | Pass | e2e "annotate mode completes 8 trades with the keyboard only": synthetic ⌘V paste events, typed reasons, Enter, J/K, Esc; then the API confirms 8 trades with entry + exit + reasoning and the inbox reads "16/20 screenshots · 8/10 reasons" |
| Coverage and unlock unit tests: gap month, year boundary, midnight UK, deleted trades, exactly 6 | Pass | `test_journal_rules.py` (9) and `test_deleted_trades_do_not_count_towards_coverage` |
| A member gets 403 on the admin's strategy and trades and sees the read-only banner | Pass | `test_member_gets_403_on_the_admins_strategy_and_trades` (9 writes refused); e2e "a member sees the admin's strategy read-only" |
| `make lint`, `make test`, `make smoke` green | Pass | lint clean (ruff, oxlint, tsc, bundle 184.1 KB of 200); 208 pytest; 76 Playwright |
| `/check-devices` clean at all six widths for the journal screens, Annotate mode and the matcher | Pass | `docs/check-devices/2026-11-06/` (48 screenshots of journal, strategy, backtest tab, trade, annotate, match, trash, hub at 360/375/430/768/1440/1920). Fixed on the way: the Annotate overlay sat under the sidebar (portal), session rows overflowed on the phone, the tablet header squeezed the title, the trade table wrapped dates |
| design-reviewer: no blockers or majors | Pass | First pass: 0 blockers, 6 majors (reserved green/orange used for status, a fake-timed import stepper, a 3.4:1 kbd, a stretched row link, a scrolling table on tablet), all fixed plus 16 of the 22 minors/nits. Second pass: 0 blockers, 1 new major (the stepper's scroll reset was a no-op inside the Radix dialog), fixed, plus its minors (observable import stages, sticky Date column, matcher card style, step dots, duplicate scroll lock, Reduced-motion rule for `page-enter` utilities). Left as minors: Sparkline/StatTile sharing, extra panels at 1920+, a few `.num` labels, drawn checkbox ticks |

## Assumptions
1. **Duplicate key is (strategy, destination kind, FX Replay id)**, not (strategy, id). The gate asks for an Ideal import followed by a Backtest import of the same file that takes *all* trades, then a third import that is all duplicates; that only works if the ideal catalogue and the backtest ledger are separate destinations. A winner can therefore sit in both. Within a destination a re-import skips duplicates and reports them.
2. The table is `journal_sessions` (model `JournalSession`) because `sessions` is already the sign-in table.
3. Members log trades only into their own strategies; the admin can log into anyone's, and those trades keep the strategy owner's `owner_id` so Mine/Others stays honest.
4. Timezone choices are limited to `Europe/London` and `UTC`, as the prompt says. Manual quick-log times use the browser's own zone and are stored as UTC.
5. Capture-time matching uses the file's own time (EXIF, name, or last-modified) against the trade's open/close in the strategy's timezone, as specified. For replayed trades those rarely coincide, so a third "sequence" pass lays leftover files into empty slots in trade order at low confidence; that is what makes FX Replay's hash-named `/screenshot` downloads usable.
6. Screenshot slots: a new Entry or Exit replaces the old one; extras cap at 3; the matcher swaps when you drop onto a filled slot.
7. The strategy profile needs the unlock *or* "Open early"; it is cached on the strategy row keyed by trade count + latest `updated_at`.
8. The "next month to replay" is the most recent gap in the months grid (filling it joins the current run to the one before), or the month after the last covered one.
9. Breakeven uses the signed-in user's threshold at import time; the stored `outcome` doesn't change if the threshold changes later (Prompt 3 analytics can recompute from `pnl`).
10. The Hub island mini-stat was wired now rather than left for the Hub prompt, since the endpoint existed.
11. `Samples/` (Jamie's real files, found in the repo root rather than `~/TradingPortal/samples/`) is git-ignored and was read only.

## Open questions for Jamie
1. Does FX Replay's `tags` column separate tags with `;`, `,` or `|`? The sample has none; all three are accepted.
2. Are your `/screenshot` files always hash-named? If FX Replay can name them with the trade id, matching becomes exact instead of by order.
3. Should the chart timezone be a per-import choice as well as a strategy default (it is now), or locked to the strategy?
4. Should a winner imported as Ideal also count in the Backtest ledger automatically, or stay a separate import (current)?
5. Rulebook default has 4 rules; want different defaults per strategy template?
6. Reasoning template fields are fixed per strategy at creation; should editing the template later re-key old trades' reasoning?
7. Session windows are Asia 00–08, London 08–13, New York 13–22 UK time; keep these?
8. Missed setups: one screenshot and a reason, kept out of P&L. Should they appear in the Annotate stepper too?

## Known issues
- Real screenshots match by sequence only (see the gate row): no filename hint and no capture time to go on.
- Design-review minors left open: `Sparkline` lives under journal rather than `components/ui`; the strategy page is one column at 1920+ (Coverage and the profile could sit beside the trade list); a handful of labels lack `.num`; native checkboxes in Annotate (the shared drawn-tick Checkbox can come with Prompt 3); the Reduced-motion rule for `animate-[page-enter_…]` utilities is a CSS attribute-selector in `index.css`.
- Phase 1's e2e toast assertions were flaky against Radix's aria-live duplicate; made exact in this branch.
- Analytics tab is a placeholder with four headline tiles until Prompt 3.
- The "live" dot on the Replay Journal nav item is static.
- Context7 MCP still rejects calls; library APIs were read from the installed packages.
- The Pillow warning about the deprecated `httpx` TestClient path is from Starlette, unchanged from Phase 1.

## Jamie's check (15 min)
1. `make dev`, sign in, open **Replay Journal**. Click **+ New strategy**: name it, instruments `NAS100`, timeframes `5m`, leave the rulebook, **Create strategy**.
2. **Import CSV** → choose `~/Desktop/Trading Portal/Samples/02:11:26 Backtest x8 Trades.csv`. The preview shows 8 of 8 rows, dates 2–25 Feb 2026, 8 winners. Keep **Ideal · 8 winners**, click **Import 8 trades**, watch the four stages, then **Add the screenshots**.
3. Drop all 21 PNGs from `Samples/` onto the matcher. They land in order at "Guess" (hash names, no capture time): drag any that are wrong, then **Save all**. You land in Annotate mode.
4. In Annotate mode: ⌘V a chart from FX Replay (right-click → Copy image) into Entry, ⌘V again for Exit, type the HTF bias, Enter through the fields, tick the rules, J for the next trade, Esc when done. The session row now reads "8 trades · 16/16 screenshots · 8/8 reasons".
5. Click **Recap** on the session: trades, win rate, total R, rules followed, the best trade's screenshot; type one thing to improve.
6. Open the **Backtest** tab: it's locked at 1/6 months. **Open early** to see the profile. **Import CSV** again with the Backtest destination: 8 trades, then a third time: every row a duplicate.
7. Click the undo arrow on a session: the toast offers Undo; use it.
8. On the phone (or a 375px window): the **+** button → pick the strategy → log an ideal trade with a photo from the camera roll.
9. **Start session** shows the brief: next month to replay, rules, your improve note.
10. Delete the test strategy, then restore it from the Trash link on the strategies page.
