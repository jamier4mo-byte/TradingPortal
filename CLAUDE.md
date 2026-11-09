# Trading Portal: notes for Claude Code

A multi-tool web app for Jamie and a few mates: a **Hub** (greeting, today's news, launch islands, live watchlist, streaks and bests), the **Replay Journal** (FX Replay import, ideal trades, backtests, analytics, Export for AI) and the **News Room** (calendar, timeline, event detail, week ahead, push alerts). v1 is complete (five build prompts, `docs/build/FINAL-REPORT.md`); the old Replay Journal repo was reference only. The team calendar was retired in the first amends (`docs/build/AMENDS-01-REPORT.md`): its API and tables stay, the UI is gone.

## Read first
- `docs/planning/trading-portal-foundations.md`: what we're building, look and feel, motion, devices, and each tool's spec.
- `docs/planning/trading-portal-review-and-build-kit.md`: top 10 actions, doc fixes F1–F19, build order, settled decisions, and the libraries to use.
- `docs/build/FINAL-REPORT.md` and `PHASE-1…5-REPORT.md`: what was built, assumptions, open questions, known issues.
- `.claude/skills/trading-portal-tokens/SKILL.md`: design tokens and rules. Use them; never hard-code a hex value.

## Stack
- `backend/`: FastAPI + SQLAlchemy 2 + Alembic + SQLite (WAL), on Python ≥ 3.12 (CI and Docker use 3.14). The venv is `backend/.venv`. Screenshots go through the `Storage` interface (`LocalStorage` or `S3Storage` for Tigris, `STORAGE_BACKEND=local|s3`). An in-app scheduler (DB lease) runs feeds, alerts, price reactions and the trash purge.
- `frontend/`: React 19, Vite 8, Tailwind 4 (tokens in `src/index.css` `@theme`), React Router, TanStack Query, Radix, `motion` (the only animation library), ECharts (lazy), lucide icons, a hand-written service worker (`public/sw.js`: push + offline caching) and Playwright in `frontend/e2e`.
- Deploy: Docker (with a pinned Litestream binary; `backend/entrypoint.sh` restores → migrates → replicates) → Fly.io from GitHub Actions on push to `main`. Deploys are skipped until the `FLY_API_TOKEN` secret exists. Runbook: `docs/DEPLOY.md`.

## Commands
`make setup` · `make dev` (open :5173) · `make test` · `make lint` (ruff, oxlint, tsc, bundle budget) · `make build` · `make run` · `make smoke` · `make migrate`
`make dev-secrets` (writes `TRADING_PORTAL_SECRET_KEY` into `.env`) · `make create-admin` · `make seed-dev` (fills `/tmp/tp-dev`: jamie/sam/alex, password `password-dev-1`) · `make icons` (favicons, iOS launch screens, manifest)
`make vapid` · `make news-backfill` · `make migrate-screenshots` (local → S3, idempotent) · `make restore-test` (quarterly drill, `docs/ops/RESTORE-TEST.md`) · `make audit` (npm audit + pip-audit)
Dev gallery of every shared component: `/dev/components`. Auth screens: `/login`, `/invite/:token`, `/reset/:token`. Tools: `/`, `/journal…`, `/news…`, `/markets…`, `/settings`, `/admin…`.

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
- Security headers (strict CSP: scripts `'self'` only, inline styles allowed) live in `backend/app/core/headers.py`; a new route must be classified in `backend/tests/test_route_roles.py` or that test fails.
- Never write tokens or API keys into the repo. MCP servers that need a secret are added in user scope.
- Branch for each piece of work. Don't push to `main` or deploy unless Jamie asks.
