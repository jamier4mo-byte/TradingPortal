# Trading Portal: notes for Claude Code

A multi-tool web app for Jamie and a few mates: a **Hub**, the **Replay Journal** (FX Replay backtest journal and analytics) and the **News Room**. It is a fresh build. Nothing is carried over from the old Replay Journal repo except the ideas in `docs/planning/`.

## Read first
- `docs/planning/trading-portal-foundations.md`: what we're building, look and feel, motion, devices, and each tool's spec.
- `docs/planning/trading-portal-review-and-build-kit.md`: top 10 actions, doc fixes F1–F19, build order, settled decisions, and the libraries to use.
- `.claude/skills/trading-portal-tokens/SKILL.md`: design tokens and rules. Use them; never hard-code a hex value.

## Stack
- `backend/`: FastAPI + SQLAlchemy 2 + Alembic + SQLite, on Python ≥ 3.12 (CI and Docker use 3.14). The venv is `backend/.venv`.
- `frontend/`: React 19, Vite 8, Tailwind 4 (tokens in `src/index.css` `@theme`), React Router, Radix, ECharts, lucide icons, and Playwright in `frontend/e2e`.
- Deploy: Docker → Fly.io from GitHub Actions on push to `main`. Deploys are skipped until the `FLY_API_TOKEN` secret exists.

## Commands
`make setup` · `make dev` (open :5173) · `make test` · `make lint` · `make build` · `make run` · `make smoke` · `make migrate`

## Rules
- Data lives in `TRADING_PORTAL_DATA_DIR` (default `~/TradingPortal/data`), never in the repo. Test runs use `/tmp/...`.
- **Never touch `~/ReplayJournal/data`.** That is Jamie's live journal from the old app.
- Schema changes are made only through Alembic migrations in `backend/migrations/versions/`.
- Design:
  - dark-first
  - one accent, `#2F7BFF`
  - the blue→violet gradient only on brand marks and hero moments
  - 1px borders
  - `.num` tabular figures on every number
  - reserved win/loss/news colours
  - 44px tap targets
  - WCAG 2.2 AA
  - every screen designed for phone, tablet and desktop
- After a UI change, run `/check-devices` and ask the `design-reviewer` subagent for a review.
- Never write tokens or API keys into the repo. MCP servers that need a secret are added in user scope.
- Branch for each piece of work. Don't push to `main` or deploy unless Jamie asks.
