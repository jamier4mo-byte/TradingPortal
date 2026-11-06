# Trading Portal: build masterprompts

Five prompts that build the whole Trading Portal in Claude Code, one phase at a time. Each one is self-contained: it reads the planning docs, CLAUDE.md, the tokens skill and the reports left by the earlier prompts, then builds, tests, reviews and reports without stopping to ask questions.

| # | File | Builds | Ends with |
|---|---|---|---|
| 1 | `01-foundations.md` | Sign-in, roles, invites, owners, tag vocabulary, key vault, app shell on every device, screen states, PWA basics | Gate 1: an admin and a member can sign in, and members can't edit your work |
| 2 | `02-journal-loop.md` | Strategies, FX Replay CSV import with sessions and undo, bulk screenshot matcher, Annotate mode, Ideal Trades, Backtest, coverage and unlock | Gate 2: your real NAS100 CSV and screenshots go in cleanly |
| 3 | `03-analytics-export.md` | FX Replay-parity metrics, Ideal / Backtest / Compare, charts, Monte Carlo, auto-insights, Export for AI | Gate 3: the numbers reconcile with FX Replay, and the export works in Claude |
| 4 | `04-newsroom-prices-alerts.md` | News Room (calendar, timeline, event detail, week ahead), news tagging of trades, per-user Twelve Data prices, Web Push alerts | Gate 4: alerts reach your phone and trades are tagged by news window |
| 5 | `05-hub-calendar-launch.md` | The Hub, team calendar, motion and launch screens, offline mode, backups (Litestream → Tigris), security pass, deploy runbook | Gate 5: ready to deploy, with the deploy commands written out for you |

The order follows the Build Kit: the journal loop comes before the Hub, because the Hub's tiles need its data.

## Before Prompt 1 (once)

1. Finish the setup in `docs/claude-setup/SETUP-REPORT.md` → "What you need to do (once)": run `scripts/claude-setup.sh` and add the Context7 and GitHub servers. Context7 matters most, because it stops Claude guessing library APIs.
2. **Let it run without permission prompts.** Copy the example settings into place. The local file is git-ignored and only affects your Mac:
   ```
   cp docs/build/masterprompts/settings.local.json.example .claude/settings.local.json
   ```
   This lets Claude edit files, run `make`/`npm`/`git`/tests and read the old Replay Journal folder. It still blocks `git push`, `fly deploy`, `fly secrets` and anything in `~/ReplayJournal/data`.
3. Commit or stash anything you've changed, so `main` is clean.

## Before Prompt 2

Put your real FX Replay export and its screenshots in **`~/TradingPortal/samples/`**, outside the repo. Use the 8-trade NAS100 CSV from 2 Nov plus the 16 `/screenshot` images, if you still have them. Prompt 2 tests the importer and the matcher against them, but it never copies your trades into the repo.

## Before Prompt 4 (optional but better)

Add these to `.env` in the repo root. The file is git-ignored, and you should never paste keys into the chat.
```
JBLANKED_API_KEY=...
DEV_TWELVE_DATA_KEY=...   # your free key, only for the local gate check
```
Without them, Prompt 4 builds against fakes and the live checks are left for you.

## How to run each prompt

1. Open Terminal, then `cd ~/Desktop/"Trading Portal"` and run `claude`. Start a **fresh session for every prompt**.
2. Use your strongest model at high effort for Prompts 1, 2 and 5 (`/model`).
3. Open the prompt file, copy everything below the `---` line, paste it, and press Enter.
4. Leave it running. Each prompt is a long job, probably a few hours and a lot of usage. Every step is ticked off in `docs/build/PROGRESS.md` and committed.
5. **If it stops part-way** (usage limit, crash, laptop closed), start a fresh `claude` and paste the **same** prompt again. It reads `PROGRESS.md` and carries on from the first unticked step.
6. When it finishes, read `docs/build/PHASE-N-REPORT.md`. Do the short "Jamie's check" list there, and answer any open questions in the next session before pasting the next prompt. A single message like "Answers to Phase 2 questions: …" works.

## What each prompt does on its own

- Creates a branch, `build/NN-…`, from your local `main`.
- Commits in small steps.
- Runs `make lint`, `make test`, `make smoke`, `/check-devices` and the `design-reviewer` subagent, then fixes what they find.
- Writes the phase report.
- If the gate passes, merges into **local** `main`. It never pushes or deploys; you push when you're happy (`git push`).

## Defaults the prompts use when something isn't settled

Each one is recorded in the phase report so you can change it later.

- Button text on blue stays dark ink (`#0B0F1A`). Proposed win/loss/impact colours are kept.
- Breakeven threshold is ±$10 in account currency (Jamie, 6 Nov 2026), and you can change it in Settings.
- Unlock rule: 6 consecutive calendar months, each with at least 1 ideal trade (so 6+ trades), counted by the trade's open date in UK time.
- News "surprise" colours are new tokens, not the reserved green/red, because those mean win/loss only.
- One small always-on Fly machine, so push alerts work.
- Fly app name `trading-portal-jamie` in London.
