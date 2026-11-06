# FX Replay analytics: what the help pages say (summary, 6 Nov 2026)

Source pages (fetched 6 Nov 2026): `analytic-metrics-defined`, `analyzing-your-trades-how-to-use-the-fx-replay-analytics-page`
(both loaded); `trades-and-logging` and `faqs` (no metric definitions). Summarised, not copied.

## Metrics on FX Replay's Analytics page
- **Performance tab:** Total PnL ($ and % of starting balance), Account Balance (start + P&L), Win Rate, Total Trades (with
  win/loss counts), Breakeven Trades, Breakeven Threshold (user input, **in R**).
- **Risk-reward (winners only):** Average RR, Max RR, Ideal Average RR, Max Ideal RR (best price within a week after close),
  "Could have profit/BE" (losers that were in profit first).
- **Expectancy** (shown as a bar of average win vs average loss; no formula given) and **Profit factor** (gross profit ÷ gross loss).
- **Winners / Losers:** total, best win / worst loss (% of balance), average win / loss (%), average duration, max and average
  consecutive.
- Average trade frequency (per day / week / month).
- **Drawdown tab:** Max / Min / Average Drawdown in R. FX Replay's "drawdown" is **how far price went against a winning trade
  before it closed**, winners only — not an equity drawdown.
- **Simulation tab:** Monte Carlo reshuffling trade outcomes.
- Breakdowns: by side, by session, by hour of open, by weekday, by month, a performance calendar (Dollar / % / RR).
- Filters: type, assets, side, outcome, tags, session, strategy, day/time, timezone, date range.

## Win rate and breakevens
- Win Rate = winning ÷ (winning + losing). **Breakevens are not counted** (left out of the denominator).
- Breakevens get their own card. The threshold is entered in R (e.g. 0.1 → −0.1R…+0.1R). Default not stated.

## Silent or unclear in the docs
Default BE threshold and whether its bounds are inclusive; whether breakevens break streaks; units of profit factor
($ vs R) and gross vs net; mean vs median duration; the base for "% of balance".

## How the Trading Portal maps this (decisions)
| FX Replay | Trading Portal | Note |
|---|---|---|
| Win Rate, BE excluded | `win_rate` = wins ÷ (wins + losses) | Same. Tooltip says breakevens are left out |
| BE threshold in R | ±2 in account $ (Jamie, 5 Nov) | Our threshold is $; recomputed from P&L at query time |
| Profit factor | gross $ profit ÷ gross $ loss; R version too | $ is the headline (matches FX Replay's P&L basis) |
| Average RR (winners) | `avg_win_r` | Plus `avg_r` over all trades (the doc's own) |
| Expectancy | win% × avg win − loss% × avg loss, in R and $ | FX Replay shows a bar only; formula is ours |
| Drawdown (winner retrace, R) | `avg_winner_mae_r` / `max_winner_mae_r` from MAE when entered | Plus equity drawdown peak-to-trough in R and $ (Default) |
| Max consecutive | `longest_win_streak` / `longest_loss_streak` | Breakevens are skipped (neither extend nor break) |
| Average duration | mean of closed trades, also split winners/losers | |
