# Trading Portal: one command for each thing you do day to day.
#   make setup    first-time install: Python venv (backend/.venv) and front-end packages
#   make dev      API with auto-reload on :8765 + Vite dev server on :5173 (open :5173)
#   make test     backend tests
#   make lint     ruff + oxlint + TypeScript check
#   make build    compile the front end into frontend/dist
#   make run      one process serving API + built UI on :8765
#   make smoke    end-to-end smoke suite (builds, throw-away backend, Playwright)
#   make migrate  apply database migrations
#
# Data lives in $TRADING_PORTAL_DATA_DIR (default ~/TradingPortal/data), never in the repo.

PYTHON ?= python3
PORT   ?= 8765
VENV   := backend/.venv

.PHONY: setup setup-backend setup-frontend dev dev-backend dev-frontend test lint fmt build run migrate smoke smoke-browser clean

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

lint:
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .
	cd frontend && npm run lint && npx tsc -b

fmt:
	cd backend && .venv/bin/ruff format . && .venv/bin/ruff check --fix .

build:
	cd frontend && npm run build

migrate:
	cd backend && .venv/bin/alembic upgrade head

run:
	cd backend && .venv/bin/alembic upgrade head && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port $(PORT)

smoke-browser:
	cd frontend && npx playwright install chromium

smoke: build smoke-browser
	cd frontend && npx playwright test

clean:
	rm -rf $(VENV) frontend/node_modules frontend/dist
