# Trading Portal

One place for Jamie's (and the mates') trading process. Three tools in one dark, high-resolution web app, installable on the phone:

- **Hub:** a greeting that knows the time of day and the session, today's high-impact news for your instruments, launch islands for the two tools, the team calendar, the live watchlist, and quiet process touches (first-run checklist, a showing-up streak, personal bests, the week behind beside the week ahead).
- **Replay Journal:** strategies with an Ideal Trades catalogue, FX Replay CSV import into a Backtest ledger (unlocked after six months of winners), screenshots with a bulk matcher and an Annotate mode, a rulebook, analytics that match FX Replay's own metrics plus equity, drawdown, Monte Carlo and Compare views, and an Export for AI.
- **News Room:** the economic calendar in UK time from Forex Factory and JBlanked, a countdown to the next high-impact event, the trading-day timeline with news windows, event detail with history and price reactions, the week ahead, and Web Push alerts.
- **Team calendar:** tasks with owners, categories and repeats; this-occurrence or whole-series edits; drag to move; high-impact news as faint markers.

Everyone has an account (invite only), everything has an owner, everyone can see everything, and members change only their own work. The admin manages users.

## Run it locally

```sh
make setup        # once: Python venv + npm packages
make dev-secrets  # once: writes TRADING_PORTAL_SECRET_KEY into .env
make dev          # API on :8765, UI on http://localhost:5173
```

Then `make create-admin` in another terminal, or `make seed-dev` for a throw-away data set (`/tmp/tp-dev`: jamie / sam / alex, password `password-dev-1`).

Other commands: `make test` · `make lint` (ruff, oxlint, tsc, Hub bundle budget) · `make smoke` (Playwright at 1440 and 375 px with axe) · `make build` · `make run` · `make migrate` · `make vapid` · `make news-backfill` · `make migrate-screenshots` · `make restore-test` · `make audit` · `make icons`.

Data lives in `TRADING_PORTAL_DATA_DIR` (default `~/TradingPortal/data`), never in the repo.

## Deploy

`docs/DEPLOY.md` is the step-by-step runbook: one always-on Fly.io machine in London, a 1 GB volume for SQLite, a Tigris bucket for screenshots and the Litestream backup stream, under $5 a month. Pushing to `main` runs CI and then deploys once the `FLY_API_TOKEN` secret exists. The quarterly restore drill is `docs/ops/RESTORE-TEST.md`.

## Layout

| Path | What |
|---|---|
| `backend/` | FastAPI app (`app/`), Alembic migrations, pytest; `entrypoint.sh` runs restore → migrate → serve under Litestream |
| `frontend/` | React 19 + Vite + Tailwind 4 UI, Playwright suite in `e2e/`, brand files and the service worker in `public/` |
| `docs/planning/` | Foundations doc and the review & build kit |
| `docs/build/` | One report per build phase, `FINAL-REPORT.md`, `PROGRESS.md`, the security review and the offline notes |
| `docs/DEPLOY.md`, `docs/ops/` | Deploy runbook and the restore drill |
| `.claude/`, `.mcp.json` | Claude Code hooks, `/check-devices`, the `design-reviewer` subagent, the design-tokens skill, MCP servers |
| `scripts/` | `capture.mjs` (device screenshots), `check-bundle.mjs` (Hub budget), `make-icons.mjs` (icons, launch screens, manifest) |
| `litestream.yml`, `fly.toml`, `Dockerfile` | Hosting |
