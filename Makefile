# Trading Portal: one command for each thing you do day to day.
#   make setup    first-time install: Python venv (backend/.venv) and front-end packages
#   make dev      API with auto-reload on :8765 + Vite dev server on :5173 (open :5173)
#   make test     backend tests
#   make lint     ruff + oxlint + TypeScript check + Hub bundle budget (200KB gzip)
#   make icons    regenerate favicons, apple-touch-icon and site.webmanifest from the T tile
#   make build    compile the front end into frontend/dist
#   make run      one process serving API + built UI on :8765
#   make smoke    end-to-end smoke suite (builds, throw-away backend, Playwright)
#   make migrate  apply database migrations
#   make dev-secrets   write a random TRADING_PORTAL_SECRET_KEY into .env if it's missing
#   make create-admin  create the first admin (asks for email and password)
#   make seed-dev      fill /tmp/tp-dev with an admin, two members and sample records
#
# Data lives in $TRADING_PORTAL_DATA_DIR (default ~/TradingPortal/data), never in the repo.

PYTHON ?= python3
PORT   ?= 8765
VENV   := backend/.venv

.PHONY: icons setup setup-backend setup-frontend dev dev-backend dev-frontend test lint fmt build run migrate smoke smoke-browser clean dev-secrets create-admin seed-dev

setup: setup-backend setup-frontend

setup-backend:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r backend/requirements-dev.txt
	$(VENV)/bin/pip install --no-deps -e ./backend

setup-frontend:
	cd frontend && npm install

dev:
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port $(PORT)

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && .venv/bin/pytest

lint: build
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .
	cd frontend && npm run lint && npx tsc -b && npm run check-bundle

icons:
	cd frontend && npm run icons

fmt:
	cd backend && .venv/bin/ruff format . && .venv/bin/ruff check --fix .

build:
	cd frontend && npm run build

migrate:
	cd backend && .venv/bin/alembic upgrade head

dev-secrets:
	@grep -q '^TRADING_PORTAL_SECRET_KEY=.\+' .env 2>/dev/null && echo ".env already has TRADING_PORTAL_SECRET_KEY" || \
	  (printf 'TRADING_PORTAL_SECRET_KEY=%s\n' "$$($(PYTHON) -c 'import secrets;print(secrets.token_urlsafe(48))')" >> .env && echo "Wrote TRADING_PORTAL_SECRET_KEY to .env")

create-admin:
	cd backend && .venv/bin/python -m app.cli create-admin

seed-dev:
	cd backend && TRADING_PORTAL_DATA_DIR=/tmp/tp-dev .venv/bin/python -m app.cli seed-dev

run:
	cd backend && .venv/bin/alembic upgrade head && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port $(PORT)

smoke-browser:
	cd frontend && npx playwright install chromium

smoke: build smoke-browser
	cd frontend && npx playwright test

clean:
	rm -rf $(VENV) frontend/node_modules frontend/dist
