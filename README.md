# Trading Portal

One place for Jamie's (and mates') trading process:

- **Hub:** greeting, today's news, launch islands and team calendar.
- **Replay Journal:** FX Replay CSV import, ideal trades, backtests and analytics.
- **News Room:** economic calendar, countdowns and push alerts.

Status: **fresh skeleton**. The app shell and Hub run in the new look. Everything else follows the build order in `docs/planning/trading-portal-review-and-build-kit.md`.

## Run it

```sh
make setup        # once: Python venv + npm packages
make dev          # API on :8765, UI on http://localhost:5173
```

`make run` serves the built UI and the API together on :8765 (`make build` first). Data goes to `~/TradingPortal/data`; set `TRADING_PORTAL_DATA_DIR` to change it.

## Layout

| Path | What |
|---|---|
| `backend/` | FastAPI app (`app/`), Alembic migrations, pytest |
| `frontend/` | React + Vite + Tailwind UI, Playwright smoke tests in `e2e/`, brand files in `public/brand/` |
| `docs/planning/` | Foundations doc, review & build kit, original tooling masterprompt |
| `docs/claude-setup/` | Claude Code tooling setup report and first screenshots |
| `.claude/`, `.mcp.json` | Claude Code hooks, `/check-devices`, `design-reviewer` subagent, project skills, MCP servers |
| `scripts/` | `claude-setup.sh` (Mac-side tooling installs), `capture.mjs` (device screenshots) |

## Deploy

Pushing to `main` runs CI. Deploying to Fly.io starts once the app exists and the `FLY_API_TOKEN` repo secret is set (see `fly.toml`).
